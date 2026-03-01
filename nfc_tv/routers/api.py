"""JSON API endpoints."""

import logging
import time

import requests
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from nfc_tv import load_config, save_config

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_state(request: Request):
    return request.app.state.app_state


# ── Health & Status ──────────────────────────────────────────────────────────


def _check_reachable(url: str, timeout: float = 3) -> bool:
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.ok
    except Exception:
        return False


@router.get("/health")
def health(request: Request):
    state = _get_state(request)
    config = state.config

    plex_ok = _check_reachable(
        f"http://{config['plex']['host']}:{config['plex']['port']}/identity"
    )
    roku_ok = _check_reachable(
        f"http://{config['roku']['host']}:8060/query/device-info"
    )

    healthy = state.reader_ok and plex_ok and roku_ok
    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "degraded",
            "nfc_reader": state.reader_ok,
            "plex": plex_ok,
            "roku": roku_ok,
        },
    )


@router.get("/api/status")
def status(request: Request):
    state = _get_state(request)
    config = state.config

    plex_ok = _check_reachable(
        f"http://{config['plex']['host']}:{config['plex']['port']}/identity"
    )
    roku_ok = _check_reachable(
        f"http://{config['roku']['host']}:8060/query/device-info"
    )

    events = state.get_events()
    last_scan = None
    if events:
        last = events[-1]
        last_scan = {
            "uid": last.uid,
            "title": last.title,
            "success": last.success,
            "timestamp": last.timestamp,
        }

    return {
        "nfc_reader": {
            "connected": state.reader_ok,
            "error": state.reader_error,
        },
        "plex": {"reachable": plex_ok},
        "roku": {"reachable": roku_ok},
        "last_scan": last_scan,
    }


# ── Events ───────────────────────────────────────────────────────────────────


@router.get("/api/events")
def events(request: Request):
    state = _get_state(request)
    return [
        {
            "uid": e.uid,
            "title": e.title,
            "success": e.success,
            "timestamp": e.timestamp,
        }
        for e in reversed(state.get_events())
    ]


# ── Cards CRUD ───────────────────────────────────────────────────────────────


@router.get("/api/cards")
def list_cards(request: Request):
    state = _get_state(request)
    cards = state.config.get("cards", {})
    return [{"uid": uid, **data} for uid, data in cards.items()]


@router.post("/api/cards")
def create_card(request: Request, body: dict):
    state = _get_state(request)
    uid = body["uid"]
    entry = {
        "type": body["type"],
        "title": body["title"],
        "library": body["library"],
    }
    if body.get("mode"):
        entry["mode"] = body["mode"]

    config = state.config
    if "cards" not in config:
        config["cards"] = {}
    config["cards"][uid] = entry
    save_config(config)
    state.update_config(config)

    return {"ok": True, "card": {"uid": uid, **entry}}


@router.delete("/api/cards/{uid}")
def delete_card(request: Request, uid: str):
    state = _get_state(request)
    config = state.config
    cards = config.get("cards", {})

    if uid not in cards:
        return JSONResponse(status_code=404, content={"error": "Card not found"})

    del cards[uid]
    save_config(config)
    state.update_config(config)
    return {"ok": True}


# ── Card Scan (registration rendezvous) ─────────────────────────────────────


@router.post("/api/cards/scan")
def scan_card(request: Request):
    """Long-poll: wait for the next card tap on the NFC reader."""
    state = _get_state(request)

    if not state.reader_ok:
        return JSONResponse(
            status_code=503,
            content={"error": "NFC reader not available"},
        )

    uid = state.request_scan(timeout=30.0)
    if uid is None:
        return JSONResponse(
            status_code=408, content={"error": "Scan timed out"}
        )
    return {"uid": uid}


# ── Plex Search ──────────────────────────────────────────────────────────────


@router.get("/api/plex/search")
def plex_search(request: Request, q: str = Query(..., min_length=1)):
    state = _get_state(request)
    config = state.config

    try:
        from plexapi.server import PlexServer

        base_url = f"http://{config['plex']['host']}:{config['plex']['port']}"
        server = PlexServer(base_url, config["plex"]["token"])

        results = []
        for section in server.library.sections():
            if section.type in ("movie", "show"):
                for item in section.search(q, limit=10):
                    entry = {
                        "title": item.title,
                        "type": item.type,
                        "library": section.title,
                        "year": getattr(item, "year", None),
                    }
                    if item.type == "show":
                        entry["episodes"] = len(item.episodes())
                    if item.thumb:
                        entry["thumb"] = item.thumb
                    results.append(entry)
        return results
    except Exception as e:
        logger.error("Plex search error: %s", e)
        return JSONResponse(
            status_code=502, content={"error": f"Plex error: {e}"}
        )
