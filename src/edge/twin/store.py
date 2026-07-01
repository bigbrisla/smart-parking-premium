"""In-memory, thread-safe store of the Digital Twin state.

It is the heart of the system: it holds each slot's state and applies the
transitions. It is read by the API (user requests) and written by the vision loop
running on a separate thread -> every access is protected by a Lock.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from src.edge.twin.models import Slot, SlotState


class ReservationError(Exception):
    """Raised when a reservation is not possible (slot not free)."""


class TwinStore:
    def __init__(self, slot_ids: list[str]):
        self._lock = threading.Lock()
        self._slots: dict[str, Slot] = {sid: Slot(id=sid) for sid in slot_ids}
        self._updated_at = datetime.now(timezone.utc)

    # ---- Update from the vision sensor ---------------------------------------

    def apply_detection(self, occupied_ids: set[str]) -> None:
        """Update the state from the slots detected as occupied.

        Precedence rules between sensor and reservation:
          - slot detected OCCUPIED:
              * if it was RESERVED -> becomes OCCUPIED (reservation "consumed":
                the expected car has arrived)
              * if it was FREE     -> becomes OCCUPIED
              * if it was OCCUPIED -> stays OCCUPIED
          - slot NOT detected:
              * if it was RESERVED -> stays RESERVED (the reservation protects it)
              * if it was OCCUPIED -> back to FREE (the car left)
              * if it was FREE     -> stays FREE
        """
        with self._lock:
            changed = False
            for sid, slot in self._slots.items():
                detected = sid in occupied_ids
                new_state = slot.state

                if detected:
                    if slot.state in (SlotState.FREE, SlotState.RESERVED):
                        new_state = SlotState.OCCUPIED
                else:
                    if slot.state == SlotState.OCCUPIED:
                        new_state = SlotState.FREE

                if new_state != slot.state:
                    slot.state = new_state
                    slot.reserved_by = None if new_state != SlotState.RESERVED else slot.reserved_by
                    slot.updated_at = datetime.now(timezone.utc)
                    changed = True

            if changed:
                self._updated_at = datetime.now(timezone.utc)

    # ---- Reservations (written by the bot) -----------------------------------

    def reserve(self, slot_id: str, user: str) -> Slot:
        """Reserve a free slot. Error if it does not exist or is not FREE."""
        with self._lock:
            slot = self._slots.get(slot_id)
            if slot is None:
                raise ReservationError(f"Stallo '{slot_id}' inesistente")
            if slot.state != SlotState.FREE:
                raise ReservationError(
                    f"Stallo '{slot_id}' non prenotabile (stato: {slot.state.value})"
                )
            slot.state = SlotState.RESERVED
            slot.reserved_by = user
            slot.updated_at = datetime.now(timezone.utc)
            self._updated_at = slot.updated_at
            return slot.model_copy()

    def cancel_reservation(self, slot_id: str) -> Slot:
        """Cancel a reservation: the slot returns to FREE."""
        with self._lock:
            slot = self._slots.get(slot_id)
            if slot is None:
                raise ReservationError(f"Stallo '{slot_id}' inesistente")
            if slot.state != SlotState.RESERVED:
                raise ReservationError(f"Stallo '{slot_id}' non e' riservato")
            slot.state = SlotState.FREE
            slot.reserved_by = None
            slot.updated_at = datetime.now(timezone.utc)
            self._updated_at = slot.updated_at
            return slot.model_copy()

    # ---- Reads ---------------------------------------------------------------

    def snapshot(self) -> tuple[list[Slot], datetime]:
        """Consistent copy of the current state of all slots."""
        with self._lock:
            return [s.model_copy() for s in self._slots.values()], self._updated_at

    def counts(self) -> dict[str, int]:
        """Aggregated counts per state (free/occupied/reserved/total)."""
        with self._lock:
            free = occ = res = 0
            for s in self._slots.values():
                if s.state == SlotState.FREE:
                    free += 1
                elif s.state == SlotState.OCCUPIED:
                    occ += 1
                else:
                    res += 1
            return {
                "free": free,
                "occupied": occ,
                "reserved": res,
                "total": len(self._slots),
            }
