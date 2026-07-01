"""Async HTTP client the bot uses to talk to an edge instance.

The bot is a plain CONSUMER of the Digital Twin: it reads availability and state,
writes reservations, forwards the GPS position and asks for federated suggestions.
It contains no domain logic: that all lives in the edge.
"""
from __future__ import annotations

import httpx


class EdgeError(Exception):
    """Communication error with the edge or an invalid response."""


class EdgeClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(method, url, **kwargs)
        except httpx.RequestError as e:
            # user-facing message (shown by the bot): kept in Italian
            raise EdgeError(f"Parcheggio non raggiungibile: {e}") from e
        if resp.status_code >= 400:
            detail = _safe_detail(resp)
            raise EdgeError(detail)
        return resp.json()

    async def availability(self) -> dict:
        return await self._request("GET", "/availability")

    async def state(self) -> dict:
        return await self._request("GET", "/twin/state")

    async def free_slots(self) -> list[str]:
        state = await self.state()
        return [s["id"] for s in state["slots"] if s["state"] == "free"]

    async def reserve(self, slot_id: str, user: str) -> dict:
        return await self._request(
            "POST", "/reservations", json={"slot_id": slot_id, "user": user}
        )

    async def cancel(self, slot_id: str) -> dict:
        return await self._request("DELETE", f"/reservations/{slot_id}")

    async def vehicle_position(self, lat: float, lon: float, plate: str | None) -> dict:
        return await self._request(
            "POST", "/vehicle/position", json={"lat": lat, "lon": lon, "plate": plate}
        )

    async def suggest(self) -> dict:
        return await self._request("GET", "/suggest")

    async def peers(self) -> list[dict]:
        data = await self._request("GET", "/federation/peers")
        return data.get("peers", [])


def _safe_detail(resp: httpx.Response) -> str:
    try:
        return resp.json().get("detail", f"errore {resp.status_code}")
    except Exception:
        return f"errore {resp.status_code}"
