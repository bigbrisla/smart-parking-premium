"""LOCAL GPS simulator (offline demo, no Telegram).

Generates a series of positions that progressively approach the parking entrance
and sends them to the /vehicle/position endpoint, until the barrier opens.

Usage:
    python scripts/simulate_gps.py --config config/granreno.yaml
    python scripts/simulate_gps.py --config config/granreno.yaml --start-km 2 --steps 8
"""
import _bootstrap  # noqa: F401

import argparse
import time

import httpx

from src.common.config import load_config


def main():
    parser = argparse.ArgumentParser(description="Simulate the GPS approach of a car")
    parser.add_argument("--config", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--plate", default="AB123CD")
    parser.add_argument("--start-km", type=float, default=2.0, help="initial distance north of the entrance")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between two sends")
    args = parser.parse_args()

    config = load_config(args.config)
    port = args.port or config.port
    base = f"http://{args.host}:{port}"
    ent = config.entrance

    # 1 degree of latitude ~ 111 km: we start 'start_km' to the north and approach.
    start_offset_deg = args.start_km / 111.0

    print(f"Sending positions to {base}/vehicle/position (entrance: {ent.lat}, {ent.lon})\n")
    for i in range(args.steps + 1):
        frac = 1 - (i / args.steps)             # from 1 (far) to 0 (at the entrance)
        lat = ent.lat + start_offset_deg * frac
        lon = ent.lon
        resp = httpx.post(f"{base}/vehicle/position",
                          json={"lat": lat, "lon": lon, "plate": args.plate}, timeout=5)
        d = resp.json()
        flag = "BARRIER OPEN" if d["unlocked"] else "..."
        print(f"  step {i:2d}  dist={d['distance_m']:8.1f} m  {flag}")
        if d["unlocked"]:
            print("\nThreshold reached: automatic unlock performed.")
            break
        time.sleep(args.delay)


if __name__ == "__main__":
    main()
