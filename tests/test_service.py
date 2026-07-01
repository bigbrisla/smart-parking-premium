"""Tests of ParkingService: vehicle position -> Haversine -> barrier, and availability."""
from src.common.config import (
    EntranceCfg,
    FederationCfg,
    ParkingConfig,
    SlotCfg,
    VisionCfg,
)
from src.edge.twin.service import ParkingService


def make_service(threshold_m=150.0):
    config = ParkingConfig(
        id="test",
        name="Test Park",
        port=9999,
        entrance=EntranceCfg(lat=44.4769, lon=11.2807),
        unlock_threshold_m=threshold_m,
        slots=[SlotCfg(id="P01"), SlotCfg(id="P02")],
        vision=VisionCfg(source="none"),
        federation=FederationCfg(peers=[]),
    )
    return ParkingService(config)


def test_initial_availability():
    svc = make_service()
    av = svc.get_availability()
    assert av.free == 2 and av.total == 2


def test_far_position_does_not_open_barrier():
    svc = make_service()
    res = svc.handle_vehicle_position(45.0, 11.0, "AB123CD")  # ~110 km
    assert res["unlocked"] is False
    assert svc.barrier.is_open is False


def test_near_position_opens_barrier():
    svc = make_service()
    # exactly at the entrance -> distance ~0 -> under threshold
    res = svc.handle_vehicle_position(44.4769, 11.2807, "AB123CD")
    assert res["distance_m"] < 1.0
    assert res["unlocked"] is True
    assert svc.barrier.is_open is True


def test_availability_reflects_reservation_and_detection():
    svc = make_service()
    svc.reserve("P01", "mario")
    assert svc.get_availability().free == 1
    svc.process_detection({"P02"})
    assert svc.get_availability().free == 0
