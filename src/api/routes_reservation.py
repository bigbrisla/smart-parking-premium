"""Reservation endpoints: the bot writes to the Digital Twin marking RESERVED."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import get_service
from src.edge.twin.service import ParkingService
from src.edge.twin.store import ReservationError

router = APIRouter(tags=["reservation"])


class ReservationRequest(BaseModel):
    slot_id: str
    user: str


@router.post("/reservations")
def create_reservation(req: ReservationRequest, service: ParkingService = Depends(get_service)):
    try:
        slot = service.reserve(req.slot_id, req.user)
    except ReservationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True, "slot": slot}


@router.delete("/reservations/{slot_id}")
def cancel_reservation(slot_id: str, service: ParkingService = Depends(get_service)):
    try:
        slot = service.cancel_reservation(slot_id)
    except ReservationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True, "slot": slot}
