"""Vision loop: camera -> occupancy detector -> Digital Twin update.

Runs on a daemon thread separate from the API. The detector is pluggable (classic
CV by default, YOLO optional): the runner does not know which technique is used.
It also produces an annotated frame (colored ROIs + boxes) saved as JPEG in the
service, so the dashboard can show it via the MJPEG stream.
"""
from __future__ import annotations

import logging
import threading
import time

from src.edge.twin.models import SlotState
from src.edge.twin.service import ParkingService
from src.edge.vision.approach import ApproachTracker
from src.edge.vision.camera import Camera
from src.edge.vision.occupancy import OccupancyDebouncer, build_occupancy

logger = logging.getLogger("vision")

# BGR colors for the slot state in the annotated frame
_STATE_COLOR = {
    SlotState.FREE: (0, 180, 0),       # green
    SlotState.OCCUPIED: (0, 0, 220),   # red
    SlotState.RESERVED: (0, 180, 220), # yellow/orange
}


class VisionRunner:
    def __init__(self, service: ParkingService):
        self.service = service
        self.camera = Camera(service.config.vision.source, service.config.vision.rotate)
        self.detector = build_occupancy(service.config)
        self.debouncer = OccupancyDebouncer(service.config.vision.stable_seconds)
        self._slot_ids = [s.id for s in service.config.slots]
        self.tracker = ApproachTracker(
            service.config.approach, service.config.entrance,
            diff_thresh=service.config.vision.diff_thresh,
        )
        self.period = 1.0 / max(service.config.vision.loop_fps, 0.1)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_frame = None                 # last raw frame (for background recapture)
        self._capture_reference_next = False     # background recapture request
        self._approach_info: dict | None = None  # last approach state (for render)
        self._warmup = 12                        # frames to discard at startup (camera stabilizing)

    def start(self):
        self.camera.open()
        self._thread = threading.Thread(target=self._loop, name="vision", daemon=True)
        self._thread.start()
        logger.info(
            "VisionRunner started (method=%s, source=%r)",
            self.service.config.vision.method, self.service.config.vision.source,
        )

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.camera.release()

    def request_reference_capture(self) -> bool:
        """Ask the loop to use the next frame as the new empty background."""
        if self._last_frame is None:
            return False
        self._capture_reference_next = True
        return True

    def _loop(self):
        while not self._stop.is_set():
            t0 = time.time()
            frame = self.camera.read()
            if frame is None:
                time.sleep(self.period)
                continue
            self._last_frame = frame

            # discard the first frames: the webcam (especially iPhone/Iriun) takes
            # a moment to stabilize and the background must be captured on a clean frame
            if self._warmup > 0:
                self._warmup -= 1
                time.sleep(self.period)
                continue

            # background handling for the detectors that require it (CV).
            # The same capture also serves the approach tracker.
            need_capture = self._capture_reference_next or (
                self.detector.needs_reference and not self.detector.has_reference
            )
            if need_capture:
                if self.detector.needs_reference:
                    self.detector.set_reference(frame)
                if self.tracker.enabled:
                    self.tracker.set_reference(frame)
                self._capture_reference_next = False
                logger.info("Reference background (empty parking) captured")

            occupied, boxes = self.detector.process(frame)
            # temporal filter: ignore transients (the hand passing over the slots)
            stable = self.debouncer.update(occupied, self._slot_ids)
            self.service.process_detection(stable)
            self._track_approach(frame)
            self._render(frame, boxes)

            elapsed = time.time() - t0
            time.sleep(max(0.0, self.period - elapsed))

    def _track_approach(self, frame):
        """Track the car in the lane and simulate the GPS position via Haversine."""
        if not (self.tracker.enabled and self.tracker.has_reference):
            self._approach_info = None
            return
        centroid = self.tracker.locate(frame)
        if centroid is None:
            self._approach_info = None
            return
        lat, lon, dist_sim = self.tracker.to_coords(centroid)
        res = self.service.handle_vehicle_position(lat, lon, plate="PLASTICO")
        self._approach_info = {"centroid": centroid, "dist": res["distance_m"],
                               "unlocked": res["unlocked"]}

    def _render(self, frame, boxes):
        """Draw ROIs (colored by state) and detected boxes; save the JPEG."""
        import cv2

        # approach lane + tracked car (label kept in Italian for the demo)
        roi = self.service.config.approach.road_roi
        if self.service.config.approach.enabled and roi is not None:
            x1, y1, x2, y2 = roi
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 150, 0), 2)
            cv2.putText(frame, "corsia", (x1 + 4, y2 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 150, 0), 2)
            if self._approach_info is not None:
                cx, cy = self._approach_info["centroid"]
                col = (0, 200, 0) if self._approach_info["unlocked"] else (0, 165, 255)
                cv2.circle(frame, (cx, cy), 10, col, -1)
                cv2.putText(frame, f"{self._approach_info['dist']:.0f} m", (cx + 12, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

        state_by_id = {s.id: s.state for s in self.service.get_state().slots}
        for slot in self.service.config.slots:
            if slot.roi is None:
                continue
            x1, y1, x2, y2 = slot.roi
            color = _STATE_COLOR.get(state_by_id.get(slot.id), (200, 200, 200))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, slot.id, (x1 + 4, y1 + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        for (x1, y1, x2, y2) in boxes:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 1)

        ok, buf = cv2.imencode(".jpg", frame)
        if ok:
            self.service.latest_jpeg = buf.tobytes()
