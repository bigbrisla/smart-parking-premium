"""Loading and validation of a parking instance configuration.

Each instance of the system (Gran Reno, IKEA, ...) is described by a single YAML
file in config/. It is the only thing that changes between instances: same code,
different configuration -> a genuinely federable system.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml
from pydantic import BaseModel, Field


class EntranceCfg(BaseModel):
    """GPS coordinates of the parking entrance."""
    lat: float
    lon: float


class SlotCfg(BaseModel):
    """Definition of a parking slot. The ROI is optional (absent if vision off)."""
    id: str
    roi: tuple[int, int, int, int] | None = None  # [x1, y1, x2, y2] in pixels


class VisionCfg(BaseModel):
    """Parameters of the vision module."""
    source: Union[int, str] = 0          # webcam index, video path, or "none"
    method: str = "cv"                   # "cv" (background subtraction) | "yolo"
    rotate: int = 0                      # frame rotation: 0, 90, 180, 270 (clockwise degrees)
    loop_fps: float = 8.0

    # --- "cv" method parameters (occupancy via background subtraction) ---
    diff_thresh: int = 30                # pixel difference threshold (0-255)
    occ_ratio: float = 0.10             # fraction of changed pixels to mark "occupied"
    roi_inset: int = 6                   # px trimmed from ROI edges (ignore the drawn lines)
    stable_seconds: float = 0.8          # a slot changes state only if stable for N seconds (ignore the hand)
    ignore_border_blobs: bool = True     # ignore the arm/hand entering from the frame border
    ignore_skin: bool = True             # ignore skin-colored pixels (the hand) in the occupancy computation

    # --- "yolo" method parameters (pretrained/fine-tuned detector) ---
    model: str = "yolo11n.pt"
    conf: float = 0.25
    vehicle_classes: list[int] = Field(default_factory=lambda: [2, 5, 7])

    @property
    def enabled(self) -> bool:
        """Vision is active if the source is not 'none'/None."""
        return not (self.source is None or str(self.source).lower() == "none")


class PeerCfg(BaseModel):
    """A federated parking whose public endpoint we know."""
    id: str
    name: str
    url: str


class FederationCfg(BaseModel):
    peers: list[PeerCfg] = Field(default_factory=list)


class ApproachCfg(BaseModel):
    """Approach lane: tracks a hand-moved car and simulates its GPS position.

    The car detected inside `road_roi` is projected onto the lane axis to obtain a
    progress value t in [0,1] (0 = at the barrier, 1 = far), converted into a
    simulated distance and then into GPS coordinates fed to Haversine.
    """
    enabled: bool = False
    road_roi: tuple[int, int, int, int] | None = None   # [x1,y1,x2,y2] of the lane
    barrier_edge: str = "top"            # side of the ROI near the barrier: top|bottom|left|right
    length_m: float = 300.0              # simulated lane length (meters)
    min_area_ratio: float = 0.02         # minimum area (fraction of ROI) to consider a car present


class ParkingConfig(BaseModel):
    """Full configuration of a parking instance."""
    id: str
    name: str
    port: int
    entrance: EntranceCfg
    unlock_threshold_m: float
    unlock_requires_reservation: bool = False   # the barrier opens only if there is an active reservation
    barrier_auto_close_s: float = 15.0          # seconds after which the barrier closes by itself
    slots: list[SlotCfg]
    vision: VisionCfg = Field(default_factory=VisionCfg)
    federation: FederationCfg = Field(default_factory=FederationCfg)
    approach: ApproachCfg = Field(default_factory=ApproachCfg)


def load_config(path: str | Path) -> ParkingConfig:
    """Read a YAML file and validate it into the ParkingConfig model."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # The YAML nests the basic data under the 'parking' key: flatten it.
    parking = raw.get("parking", {})
    data = {
        "id": parking.get("id"),
        "name": parking.get("name"),
        "port": parking.get("port"),
        "entrance": raw.get("entrance"),
        "unlock_threshold_m": raw.get("unlock_threshold_m"),
        "unlock_requires_reservation": raw.get("unlock_requires_reservation", False),
        "barrier_auto_close_s": raw.get("barrier_auto_close_s", 15.0),
        "slots": raw.get("slots", []),
        "vision": raw.get("vision", {}),
        "federation": raw.get("federation", {}),
        "approach": raw.get("approach", {}),
    }
    return ParkingConfig.model_validate(data)
