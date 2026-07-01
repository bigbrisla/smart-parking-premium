"""Slot occupancy detector, with a pluggable interface.

All detectors expose the same method `process(frame) -> (occupied, boxes)` so the
runner does not know which technique is underneath. Two implementations:

- CvOccupancy  : classic computer vision. Compares each ROI with a BACKGROUND
                 frame (empty parking): the printed grid and labels cancel out in
                 the difference, only the toy car stands out. Chosen as default
                 because it is robust on toy objects, where pretrained YOLO fails.
- YoloOccupancy: uses a YOLO model (useful after domain fine-tuning).

build_occupancy(config) builds the right one based on vision.method.
"""
from __future__ import annotations

from pathlib import Path

from src.common.config import ParkingConfig, SlotCfg

# return type: set of occupied slot ids + boxes to draw (xyxy)
ProcessResult = tuple[set[str], list[tuple[int, int, int, int]]]


def foreground_mask(cur_bgr, ref_bgr, diff_thresh: int):
    """Foreground mask (objects) with SHADOW SUPPRESSION.

    A shadow lowers the brightness (V) but leaves hue (H) and saturation (S)
    almost unchanged: it is therefore recognized and excluded. A car, which also
    changes color, stays in the foreground. Both frames are assumed already
    blurred (BGR). Returns a uint8 mask (0/255).
    """
    import cv2
    import numpy as np

    gray_d = cv2.absdiff(cv2.cvtColor(cur_bgr, cv2.COLOR_BGR2GRAY),
                         cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2GRAY))
    changed = gray_d > diff_thresh

    hc = cv2.cvtColor(cur_bgr, cv2.COLOR_BGR2HSV).astype(np.int16)
    hr = cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2HSV).astype(np.int16)
    Vc, Vr = hc[:, :, 2], hr[:, :, 2]
    Sc, Sr = hc[:, :, 1], hr[:, :, 1]
    dH = np.minimum(np.abs(hc[:, :, 0] - hr[:, :, 0]),
                    180 - np.abs(hc[:, :, 0] - hr[:, :, 0]))
    # shadow: darker but not black, and with the same chrominance
    shadow = (Vc < Vr) & (Vc > 0.4 * Vr) & (np.abs(Sc - Sr) < 40) & (dH < 18)

    return ((changed & ~shadow).astype(np.uint8)) * 255


def skin_mask(bgr):
    """Skin-colored pixel mask (YCrCb space), to spot the HAND.

    Skin occupies a narrow Cr/Cb range, well separated from the saturated colors
    of the toy cars (verified: hand 40-100% vs cars 5-11%).
    """
    import cv2
    import numpy as np

    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    cr, cb = ycrcb[:, :, 1], ycrcb[:, :, 2]
    # the (HSV) saturation distinguishes skin (saturated, S~140-160) from the
    # gray/white parts of the toys that would fall in the Cr/Cb range (low S).
    s = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 1]
    skin = ((cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127) & (s >= 90)).astype(np.uint8) * 255
    return cv2.morphologyEx(skin, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))


def remove_border_blobs(mask):
    """Remove from the mask the regions connected to the image BORDER.

    The arm/hand always enters from a frame border, whereas a parked car is an
    isolated interior blob. This way the hand (and arm) do not count as
    occupancy, regardless of color.
    """
    import cv2
    import numpy as np

    num, labels = cv2.connectedComponents(mask)
    if num <= 1:
        return mask
    border = np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
    border_labels = set(np.unique(border).tolist()) - {0}
    if not border_labels:
        return mask
    keep = ~np.isin(labels, list(border_labels))
    return (mask * keep).astype(mask.dtype)


class OccupancyDetector:
    needs_reference: bool = False

    @property
    def has_reference(self) -> bool:
        return True

    def set_reference(self, frame) -> None:  # noqa: D401
        """Set the background frame (only for detectors that require it)."""

    def process(self, frame) -> ProcessResult:
        raise NotImplementedError


class CvOccupancy(OccupancyDetector):
    needs_reference = True

    def __init__(self, slots: list[SlotCfg], diff_thresh: int, occ_ratio: float,
                 inset: int, ref_path: Path | None = None, ignore_border: bool = True,
                 ignore_skin: bool = True):
        self.slots = slots
        self.diff_thresh = diff_thresh
        self.occ_ratio = occ_ratio
        self.inset = inset
        self.ignore_border = ignore_border
        self.ignore_skin = ignore_skin
        self.ref_path = ref_path
        self._ref_bgr = None
        if ref_path is not None and ref_path.exists():
            import cv2
            img = cv2.imread(str(ref_path))
            if img is not None:
                self._ref_bgr = self._prep(img)

    @property
    def has_reference(self) -> bool:
        return self._ref_bgr is not None

    @staticmethod
    def _prep(frame):
        """Blur (BGR) to reduce noise; the chrominance is needed for shadows."""
        import cv2
        return cv2.GaussianBlur(frame, (5, 5), 0)

    def set_reference(self, frame) -> None:
        import cv2
        self._ref_bgr = self._prep(frame)
        if self.ref_path is not None:
            self.ref_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(self.ref_path), frame)

    def process(self, frame) -> ProcessResult:
        occupied: set[str] = set()
        boxes: list[tuple[int, int, int, int]] = []
        if self._ref_bgr is None:
            return occupied, boxes

        import cv2
        cur = self._prep(frame)
        mask = foreground_mask(cur, self._ref_bgr, self.diff_thresh)
        if self.ignore_skin:
            mask = cv2.bitwise_and(mask, cv2.bitwise_not(skin_mask(cur)))
        if self.ignore_border:
            mask = remove_border_blobs(mask)

        for slot in self.slots:
            if slot.roi is None:
                continue
            x1, y1, x2, y2 = slot.roi
            # shrink the ROI to ignore the black lines drawn at the edges
            xi1, yi1, xi2, yi2 = x1 + self.inset, y1 + self.inset, x2 - self.inset, y2 - self.inset
            if xi2 <= xi1 or yi2 <= yi1:
                continue
            sub = mask[yi1:yi2, xi1:xi2]
            ratio = float(sub.mean()) / 255.0  # fraction of changed pixels
            if ratio >= self.occ_ratio:
                occupied.add(slot.id)
                boxes.append((x1, y1, x2, y2))
        return occupied, boxes


class YoloOccupancy(OccupancyDetector):
    def __init__(self, detector, slots: list[SlotCfg]):
        self.detector = detector
        self.slots = slots

    def process(self, frame) -> ProcessResult:
        from src.edge.vision.roi import map_detections_to_slots
        dets = self.detector.detect(frame)
        occupied = map_detections_to_slots(dets, self.slots)
        boxes = [d.xyxy for d in dets]
        return occupied, boxes


class OccupancyDebouncer:
    """Temporal stability filter on the occupancy detections.

    A slot changes state (free<->occupied) only if the new detection persists for
    at least `stable_seconds`. This way the transients (the HAND passing over the
    slots while moving a car) do not change the state, whereas a genuinely parked
    car, which persists, is registered.
    """

    def __init__(self, stable_seconds: float):
        self.stable_seconds = stable_seconds
        self._committed: dict[str, bool] = {}        # confirmed state per slot
        self._pending: dict[str, tuple[bool, float]] = {}  # (value, since_when)

    def update(self, raw_occupied: set[str], slot_ids: list[str]) -> set[str]:
        import time
        now = time.time()
        for sid in slot_ids:
            raw = sid in raw_occupied
            committed = self._committed.get(sid, False)
            if raw == committed:
                self._pending.pop(sid, None)      # no change in progress
                continue
            pend = self._pending.get(sid)
            if pend is None or pend[0] != raw:
                self._pending[sid] = (raw, now)   # new candidate to change
            elif now - pend[1] >= self.stable_seconds:
                self._committed[sid] = raw        # stable long enough: confirm
                self._pending.pop(sid, None)
        return {sid for sid, occ in self._committed.items() if occ}


def build_occupancy(config: ParkingConfig) -> OccupancyDetector:
    v = config.vision
    if v.method == "yolo":
        from src.edge.vision.detector import YoloDetector
        det = YoloDetector(v.model, v.conf, v.vehicle_classes)
        return YoloOccupancy(det, config.slots)
    # default: classic CV, with background persisted in data/<id>_bg.png
    ref_path = Path("data") / f"{config.id}_bg.png"
    return CvOccupancy(config.slots, v.diff_thresh, v.occ_ratio, v.roi_inset,
                       ref_path, v.ignore_border_blobs, v.ignore_skin)
