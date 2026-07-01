"""Haversine formula implemented by hand (no external library).

Computes the distance in meters between two points on the Earth's surface given
latitude and longitude in decimal degrees, approximating the Earth as a sphere.
"""
from __future__ import annotations

import math

# Mean Earth radius in meters.
EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between (lat1, lon1) and (lat2, lon2).

    Steps of the formula:
      1) convert coordinates from degrees to radians
      2) compute the latitude and longitude differences
      3) apply the haversine formula
      4) multiply the angular distance by the Earth's radius
    """
    # 1) degrees -> radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    # 2) differences
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # 3) the haversine 'a' term
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )

    # central angular distance (atan2 is numerically more stable than asin)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # 4) linear distance
    return EARTH_RADIUS_M * c
