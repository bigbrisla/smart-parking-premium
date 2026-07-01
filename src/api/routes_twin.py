"""Digital Twin read endpoints + debug utility."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.deps import get_service
from src.edge.twin.models import ParkingStateResponse
from src.edge.twin.service import ParkingService

router = APIRouter(tags=["twin"])


@router.get("/twin/state", response_model=ParkingStateResponse)
def get_twin_state(service: ParkingService = Depends(get_service)):
    """Detailed state of all slots (internal use / dashboard)."""
    return service.get_state()


class DebugOccupyRequest(BaseModel):
    occupied_ids: list[str]


@router.post("/twin/debug/occupy")
def debug_occupy(req: DebugOccupyRequest, service: ParkingService = Depends(get_service)):
    """Force the occupied/free state without a webcam (useful for IKEA and tests)."""
    service.process_detection(set(req.occupied_ids))
    return service.get_state()
