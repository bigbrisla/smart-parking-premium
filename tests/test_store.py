"""Tests of the Digital Twin store: reservations and state transitions."""
import pytest

from src.edge.twin.models import SlotState
from src.edge.twin.store import ReservationError, TwinStore


def make_store():
    return TwinStore(["P01", "P02", "P03"])


# ---- Reservations -----------------------------------------------------------

def test_reserve_free_slot():
    s = make_store()
    slot = s.reserve("P01", "mario")
    assert slot.state == SlotState.RESERVED
    assert slot.reserved_by == "mario"
    assert s.counts() == {"free": 2, "occupied": 0, "reserved": 1, "total": 3}


def test_reserve_already_reserved_fails():
    s = make_store()
    s.reserve("P01", "mario")
    with pytest.raises(ReservationError):
        s.reserve("P01", "luigi")


def test_reserve_nonexistent_slot_fails():
    s = make_store()
    with pytest.raises(ReservationError):
        s.reserve("ZZZ", "mario")


def test_cancel_reservation_becomes_free():
    s = make_store()
    s.reserve("P01", "mario")
    slot = s.cancel_reservation("P01")
    assert slot.state == SlotState.FREE
    assert slot.reserved_by is None


def test_cancel_on_non_reserved_slot_fails():
    s = make_store()
    with pytest.raises(ReservationError):
        s.cancel_reservation("P01")


# ---- Transitions from detection (sensor <-> reservation precedence) ---------

def state_of(store, sid):
    slots, _ = store.snapshot()
    return {x.id: x.state for x in slots}[sid]


def test_detection_free_becomes_occupied():
    s = make_store()
    s.apply_detection({"P01"})
    assert state_of(s, "P01") == SlotState.OCCUPIED


def test_detection_occupied_disappears_becomes_free():
    s = make_store()
    s.apply_detection({"P01"})
    s.apply_detection(set())            # the car has left
    assert state_of(s, "P01") == SlotState.FREE


def test_reserved_without_car_stays_reserved():
    s = make_store()
    s.reserve("P01", "mario")
    s.apply_detection(set())            # no car detected
    assert state_of(s, "P01") == SlotState.RESERVED


def test_reserved_with_car_becomes_occupied():
    s = make_store()
    s.reserve("P01", "mario")
    s.apply_detection({"P01"})          # the expected car arrives
    assert state_of(s, "P01") == SlotState.OCCUPIED
    # reservation consumed: no trace of reserved_by remains
    slots, _ = s.snapshot()
    assert {x.id: x.reserved_by for x in slots}["P01"] is None
