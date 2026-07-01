"""Federation client: queries the peer parkings via HTTP.

Downloads ONLY the aggregate figure (/federation/availability) of each peer, as
per the B2B model. Used both by the dashboard and by the bot to suggest alternatives.
"""
from __future__ import annotations

import logging

import httpx

from src.common.config import PeerCfg

logger = logging.getLogger("federation")


def fetch_peer_availability(peer: PeerCfg, timeout: float = 2.0) -> dict | None:
    """Return {id, name, free, total, url, online} for a peer, or None if unreachable."""
    try:
        r = httpx.get(f"{peer.url}/federation/availability", timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return {
            "id": data.get("parking_id", peer.id),
            "name": data.get("name", peer.name),
            "free": data.get("free", 0),
            "total": data.get("total", 0),
            "url": peer.url,
            "online": True,
        }
    except Exception as e:  # peer offline or network error: degrade gracefully
        logger.warning("Peer %s unreachable: %s", peer.id, e)
        return {"id": peer.id, "name": peer.name, "free": 0, "total": 0,
                "url": peer.url, "online": False}


def fetch_all_peers(peers: list[PeerCfg]) -> list[dict]:
    return [fetch_peer_availability(p) for p in peers]
