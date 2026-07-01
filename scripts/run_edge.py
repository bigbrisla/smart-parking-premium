"""Start an edge instance (Digital Twin + vision + API).

Usage:
    python scripts/run_edge.py --config config/granreno.yaml
    python scripts/run_edge.py --config config/ikea.yaml
"""
import _bootstrap  # noqa: F401  (sets up sys.path)

import argparse

import uvicorn

from src.api.main import create_app
from src.common.config import load_config


def main():
    parser = argparse.ArgumentParser(description="Start a Smart Parking Premium instance")
    parser.add_argument("--config", required=True, help="path to the YAML configuration file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None, help="override the config port")
    parser.add_argument("--no-vision", action="store_true",
                        help="disable the webcam (useful to try bot/API without the mockup)")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.no_vision:
        config.vision.source = "none"
    port = args.port or config.port
    app = create_app(config)
    print(f"\n  {config.name}")
    print(f"  Dashboard:  http://{args.host}:{port}/")
    print(f"  API docs:   http://{args.host}:{port}/docs\n")
    uvicorn.run(app, host=args.host, port=port)


if __name__ == "__main__":
    main()
