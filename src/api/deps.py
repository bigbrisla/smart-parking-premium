"""Shared dependency: retrieves the ParkingService from the app state."""
from __future__ import annotations

from fastapi import Request

from src.edge.twin.service import ParkingService


def get_service(request: Request) -> ParkingService:
    return request.app.state.service
