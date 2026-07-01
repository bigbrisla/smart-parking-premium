"""Wrapper around YOLOv11 (Ultralytics) for vehicle detection.

ultralytics/torch are imported LAZILY (only when actually needed), so the API and
the dashboard work even before the heavy packages are installed, or on an instance
with vision disabled (e.g. IKEA).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Detection:
    """A detection: COCO class, confidence and bounding box in pixels."""
    cls_id: int
    conf: float
    xyxy: tuple[int, int, int, int]  # (x1, y1, x2, y2)

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.xyxy
        return (x1 + x2) // 2, (y1 + y2) // 2


class YoloDetector:
    def __init__(self, model_path: str = "yolo11n.pt", conf: float = 0.25,
                 vehicle_classes: list[int] | None = None):
        self.model_path = model_path
        self.conf = conf
        # COCO classes considered "vehicle": 2=car, 5=bus, 7=truck (3=motorcycle optional)
        self.vehicle_classes = set(vehicle_classes or [2, 5, 7])
        self._model = None  # lazily loaded

    def _ensure_model(self):
        if self._model is None:
            from ultralytics import YOLO  # lazy import
            self._model = YOLO(self.model_path)
        return self._model

    def detect(self, frame) -> list[Detection]:
        """Run detection on a BGR frame (numpy) and filter the vehicles."""
        model = self._ensure_model()
        results = model.predict(frame, conf=self.conf, verbose=False)
        detections: list[Detection] = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id not in self.vehicle_classes:
                    continue
                conf = float(box.conf[0])
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                detections.append(Detection(cls_id, conf, (x1, y1, x2, y2)))
        return detections
