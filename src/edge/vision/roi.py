"""Mapping of detections onto the slot ROIs.

Each slot has a rectangular ROI [x1, y1, x2, y2] in pixels. A slot is considered
OCCUPIED if the center of at least one vehicle bounding box falls inside its ROI.
It is the simplest and most robust rule for the mockup: independent of the car
scale and little sensitive to noise.
"""
from __future__ import annotations

from src.common.config import SlotCfg
from src.edge.vision.detector import Detection


def _point_in_rect(px: int, py: int, rect: tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = rect
    return x1 <= px <= x2 and y1 <= py <= y2


def map_detections_to_slots(detections: list[Detection], slots: list[SlotCfg]) -> set[str]:
    """Return the set of occupied slot ids given the detections."""
    occupied: set[str] = set()
    for slot in slots:
        if slot.roi is None:
            continue
        for det in detections:
            cx, cy = det.center
            if _point_in_rect(cx, cy, slot.roi):
                occupied.add(slot.id)
                break
    return occupied
