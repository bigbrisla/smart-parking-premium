"""Tests of the Haversine formula (run with: pytest)."""
import math

from src.edge.geo.haversine import haversine_m


def test_zero_distance():
    assert haversine_m(44.5, 11.3, 44.5, 11.3) == 0.0


def test_symmetry():
    a = haversine_m(44.476, 11.280, 44.477, 11.289)
    b = haversine_m(44.477, 11.289, 44.476, 11.280)
    assert math.isclose(a, b, rel_tol=1e-9)


def test_one_degree_of_latitude():
    # 1 degree of latitude ~ 111 km. 1% tolerance for the spherical approximation.
    d = haversine_m(44.0, 11.0, 45.0, 11.0)
    assert math.isclose(d, 111_000, rel_tol=0.01)


def test_known_distance_bologna_milan():
    # Bologna -> Milan ~ 200 km as the crow flies. Generous tolerance.
    bologna = (44.4949, 11.3426)
    milan = (45.4642, 9.1900)
    d = haversine_m(*bologna, *milan) / 1000  # km
    assert 190 < d < 220
