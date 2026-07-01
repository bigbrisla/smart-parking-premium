"""FastAPI app factory for a single parking instance (one Digital Twin).

Starts the vision loop in the background (if vision is enabled), mounts the
routers and serves the dashboard and the annotated MJPEG stream.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from src.api import (
    routes_federation,
    routes_reservation,
    routes_twin,
    routes_vehicle,
    routes_vision,
)
from src.common.config import ParkingConfig
from src.edge.twin.service import ParkingService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

_WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def create_app(config: ParkingConfig) -> FastAPI:
    service = ParkingService(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runner = None
        if config.vision.enabled:
            # lazy import: the app starts even without ultralytics/opencv if vision is off
            from src.edge.runner import VisionRunner
            runner = VisionRunner(service)
            try:
                runner.start()
            except Exception as e:
                logging.getLogger("vision").error("Vision not started: %s", e)
                runner = None
        app.state.vision_runner = runner
        yield
        if runner is not None:
            runner.stop()

    app = FastAPI(title=f"Smart Parking Premium - {config.name}", lifespan=lifespan)
    app.state.service = service

    app.include_router(routes_twin.router)
    app.include_router(routes_reservation.router)
    app.include_router(routes_vehicle.router)
    app.include_router(routes_federation.router)
    app.include_router(routes_vision.router)

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        html = (_WEB_DIR / "dashboard.html").read_text(encoding="utf-8")
        return HTMLResponse(html)

    @app.get("/video")
    def video():
        """MJPEG stream of the frame annotated by the vision (if available)."""
        def gen():
            boundary = b"--frame"
            while True:
                jpeg = service.latest_jpeg
                if jpeg is not None:
                    yield (boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n"
                           + jpeg + b"\r\n")
                time.sleep(0.1)
        return StreamingResponse(
            gen(), media_type="multipart/x-mixed-replace; boundary=frame"
        )

    return app
