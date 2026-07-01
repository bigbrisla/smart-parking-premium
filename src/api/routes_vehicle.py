"""Vehicle position endpoint: Haversine -> barrier unlock (edge/local logic)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.deps import get_service
from src.edge.twin.service import ParkingService

router = APIRouter(tags=["vehicle"])


class VehiclePosition(BaseModel):
    lat: float
    lon: float
    plate: str | None = None


@router.post("/vehicle/position")
def post_vehicle_position(pos: VehiclePosition, service: ParkingService = Depends(get_service)):
    """Receive the car's GPS position and open the barrier if under threshold."""
    return service.handle_vehicle_position(pos.lat, pos.lon, pos.plate)


@router.get("/barrier")
def barrier_status(service: ParkingService = Depends(get_service)):
    return service.barrier.status()
