"""Tracker of the approaching car along the lane (to simulate live GPS).

Uses the same background subtraction technique as the occupancy detector: it finds
the car (the region "changed" with respect to the background) inside the lane,
computes its centroid, projects it onto the lane axis to obtain the progress and
converts it into simulated GPS coordinates to feed to Haversine.
"""
from __future__ import annotations

from src.common.config import ApproachCfg, EntranceCfg

# 1 degree of latitude ~ 111 km
_DEG_PER_M = 1.0 / 111_000.0


class ApproachTracker:
    def __init__(self, cfg: ApproachCfg, entrance: EntranceCfg, diff_thresh: int = 30):
        self.cfg = cfg
        self.entrance = entrance
        self.diff_thresh = diff_thresh
        self._ref_bgr = None

    @property
    def enabled(self) -> bool:
        return self.cfg.enabled and self.cfg.road_roi is not None

    @property
    def has_reference(self) -> bool:
        return self._ref_bgr is not None

    @staticmethod
    def _prep(frame):
        import cv2
        return cv2.GaussianBlur(frame, (5, 5), 0)

    def set_reference(self, frame) -> None:
        self._ref_bgr = self._prep(frame)

    def locate(self, frame) -> tuple[int, int] | None:
        """Centroid (in pixels) of the CAR in the lane, or None if absent.

        Takes the largest connected blob (the car), not the barycenter of all the
        changed pixels: this way scattered noise / light drift does not shift the
        estimated position.
        """
        import cv2
        import numpy as np
        from src.edge.vision.occupancy import foreground_mask, skin_mask
        if self._ref_bgr is None or self.cfg.road_roi is None:
            return None
        x1, y1, x2, y2 = self.cfg.road_roi
        cur = self._prep(frame)
        mask = foreground_mask(cur, self._ref_bgr, self.diff_thresh)
        # remove the hand (skin) so only the dragged car remains
        mask = cv2.bitwise_and(mask, cv2.bitwise_not(skin_mask(cur)))
        sub = mask[y1:y2, x1:x2]
        if sub.size == 0:
            return None
        # morphological opening: removes scattered noise (isolated pixels)
        sub = cv2.morphologyEx(sub, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        largest = max(cnts, key=cv2.contourArea)
        road_area = (x2 - x1) * (y2 - y1)
        if cv2.contourArea(largest) < self.cfg.min_area_ratio * road_area:
            return None
        m = cv2.moments(largest)
        if m["m00"] == 0:
            return None
        cx = x1 + int(m["m10"] / m["m00"])
        cy = y1 + int(m["m01"] / m["m00"])
        return cx, cy

    def progress(self, centroid: tuple[int, int]) -> float:
        """Progress t in [0,1]: 0 = at the barrier, 1 = far end."""
        x1, y1, x2, y2 = self.cfg.road_roi
        cx, cy = centroid
        edge = self.cfg.barrier_edge
        if edge == "top":
            t = (cy - y1) / max(1, (y2 - y1))
        elif edge == "bottom":
            t = (y2 - cy) / max(1, (y2 - y1))
        elif edge == "left":
            t = (cx - x1) / max(1, (x2 - x1))
        else:  # right
            t = (x2 - cx) / max(1, (x2 - x1))
        return min(1.0, max(0.0, t))

    def to_coords(self, centroid: tuple[int, int]) -> tuple[float, float, float]:
        """Map the centroid to (lat, lon, simulated_distance_m).

        The simulated distance is t * length_m; the GPS position is the entrance
        shifted north by that distance, so that Haversine recovers it.
        """
        t = self.progress(centroid)
        dist_m = t * self.cfg.length_m
        lat = self.entrance.lat + dist_m * _DEG_PER_M
        lon = self.entrance.lon
        return lat, lon, dist_m
