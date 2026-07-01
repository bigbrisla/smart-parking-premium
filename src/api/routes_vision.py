"""Vision management endpoint (CV method: capture of the empty background)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["vision"])


@router.post("/vision/reference")
def capture_reference(request: Request):
    """Use the current frame as the new "empty parking" background (CV method).

    To be called with the mockup WITHOUT cars, at the start of the demo or when
    the lighting/framing changes.
    """
    runner = getattr(request.app.state, "vision_runner", None)
    if runner is None:
        raise HTTPException(status_code=409, detail="Vision non attiva su questa istanza")
    if not runner.request_reference_capture():
        raise HTTPException(status_code=503, detail="Nessun frame disponibile dalla camera")
    return {"ok": True, "message": "Sfondo aggiornato al prossimo frame"}
