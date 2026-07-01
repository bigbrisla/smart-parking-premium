"""Federation endpoints: expose ONLY the aggregate availability figure.

It is the B2B boundary between different owners: a federated parking can know how
many spots are free, but NOT the detailed slot-by-slot state.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_service
from src.edge.twin.models import AvailabilityResponse
from src.edge.twin.service import ParkingService
from src.federation.client import fetch_all_peers

router = APIRouter(tags=["federation"])


@router.get("/availability", response_model=AvailabilityResponse)
def availability(service: ParkingService = Depends(get_service)):
    """Aggregate availability of THIS parking (also used by the dashboard)."""
    return service.get_availability()


@router.get("/federation/availability", response_model=AvailabilityResponse)
def federation_availability(service: ParkingService = Depends(get_service)):
    """Same aggregate, exposed on the endpoint dedicated to B2B federation."""
    return service.get_availability()


@router.get("/federation/peers")
def federation_peers(service: ParkingService = Depends(get_service)):
    """Query the federated parkings live and return their aggregate availability."""
    return {"peers": fetch_all_peers(service.config.federation.peers)}


@router.get("/suggest")
def suggest(service: ParkingService = Depends(get_service)):
    """Federation use case: if this parking is full, propose alternatives.

    Returns the federated facilities with free spots, sorted by availability.
    """
    local = service.get_availability()
    suggestions = [p for p in fetch_all_peers(service.config.federation.peers)
                   if p["online"] and p["free"] > 0]
    suggestions.sort(key=lambda p: p["free"], reverse=True)
    return {
        "parking_id": local.parking_id,
        "name": local.name,
        "free": local.free,
        "is_full": local.free == 0,
        "suggestions": suggestions,
    }
