"""Digital Twin facade for a parking instance.

It ties together the store (slot state), the barrier and geolocation, and is the
only object the API knows about. It exposes the high-level operations: update from
detection, reservations, vehicle position handling, state and availability.
"""
from __future__ import annotations

import logging

from src.common.config import ParkingConfig
from src.edge.barrier.simulator import BarrierSimulator
from src.edge.geo.haversine import haversine_m
from src.edge.twin.models import (
    AvailabilityResponse,
    ParkingStateResponse,
)
from src.edge.twin.store import TwinStore

logger = logging.getLogger("twin")


class ParkingService:
    def __init__(self, config: ParkingConfig):
        self.config = config
        self.store = TwinStore([s.id for s in config.slots])
        self.barrier = BarrierSimulator(auto_close_after_s=config.barrier_auto_close_s)
        # latest annotated frame (JPEG) produced by the vision, for the MJPEG stream
        self.latest_jpeg: bytes | None = None

    # ---- Vision sensor -------------------------------------------------------

    def process_detection(self, occupied_ids: set[str]) -> None:
        self.store.apply_detection(occupied_ids)

    # ---- Reservations --------------------------------------------------------

    def reserve(self, slot_id: str, user: str):
        return self.store.reserve(slot_id, user)

    def cancel_reservation(self, slot_id: str):
        return self.store.cancel_reservation(slot_id)

    # ---- Vehicle position + barrier (Haversine) ------------------------------

    def handle_vehicle_position(self, lat: float, lon: float, plate: str | None) -> dict:
        """Compute the distance from the entrance and open the barrier if under threshold.

        If `unlock_requires_reservation` is enabled, the barrier opens only when
        there is at least one active reservation (RESERVED state).
        """
        entrance = self.config.entrance
        distance = haversine_m(lat, lon, entrance.lat, entrance.lon)
        threshold = self.config.unlock_threshold_m
        within = distance <= threshold

        has_reservation = self.store.counts()["reserved"] > 0
        blocked_no_reservation = (
            within and self.config.unlock_requires_reservation and not has_reservation
        )
        unlocked = within and not blocked_no_reservation

        if unlocked:
            who = plate or "vehicle"
            self.barrier.open(reason=f"{who} at {distance:.0f} m (threshold {threshold:.0f} m)")

        logger.info(
            "Vehicle position %s: distance %.1f m -> %s",
            plate or "?",
            distance,
            "UNLOCK" if unlocked else ("no reservation" if blocked_no_reservation else "out of range"),
        )
        return {
            "plate": plate,
            "distance_m": round(distance, 1),
            "threshold_m": threshold,
            "unlocked": unlocked,
            "blocked_no_reservation": blocked_no_reservation,
            "barrier": self.barrier.status(),
        }

    # ---- Reads ---------------------------------------------------------------

    def get_state(self) -> ParkingStateResponse:
        slots, updated_at = self.store.snapshot()
        c = self.store.counts()
        return ParkingStateResponse(
            parking_id=self.config.id,
            name=self.config.name,
            total=c["total"],
            free=c["free"],
            occupied=c["occupied"],
            reserved=c["reserved"],
            slots=slots,
            updated_at=updated_at,
        )

    def get_availability(self) -> AvailabilityResponse:
        """Only the aggregate: it is the sole datum shared in federation."""
        c = self.store.counts()
        return AvailabilityResponse(
            parking_id=self.config.id,
            name=self.config.name,
            free=c["free"],
            total=c["total"],
        )
