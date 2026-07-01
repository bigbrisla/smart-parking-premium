"""Digital Twin data models: the slot and the responses exposed by the API."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SlotState(str, Enum):
    """Possible states of a slot in the Digital Twin.

    3-state machine with explicit precedence handled in store.py:
    - FREE      free (sensor sees no car, no reservation)
    - OCCUPIED  occupied (detected by the vision sensor)
    - RESERVED  reserved via bot; "overrides" the sensor until the car arrives
    """
    FREE = "free"
    OCCUPIED = "occupied"
    RESERVED = "reserved"


class Slot(BaseModel):
    """Current state of a single slot (digital twin of the physical slot)."""
    id: str
    state: SlotState = SlotState.FREE
    reserved_by: str | None = None
    updated_at: datetime = Field(default_factory=_now)


# ---- API response models ----------------------------------------------------

class ParkingStateResponse(BaseModel):
    """DETAILED twin state (exposed only internally / to the dashboard)."""
    parking_id: str
    name: str
    total: int
    free: int
    occupied: int
    reserved: int
    slots: list[Slot]
    updated_at: datetime


class AvailabilityResponse(BaseModel):
    """AGGREGATE availability figure (the only one shared in federation)."""
    parking_id: str
    name: str
    free: int
    total: int
