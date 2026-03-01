"""FastAPI application with NFC daemon lifecycle management."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from nfc_tv import load_config
from nfc_tv.daemon import NFCDaemon
from nfc_tv.state import AppState

logger = logging.getLogger(__name__)

_here = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    state = AppState(config)
    app.state.app_state = state

    daemon = NFCDaemon(state)
    daemon.start()
    logger.info("NFC daemon thread started")

    yield

    daemon.stop()
    daemon.join(timeout=5)
    logger.info("NFC daemon thread stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="NFC-TV", lifespan=lifespan)

    # Mount static files
    app.mount("/static", StaticFiles(directory=_here / "static"), name="static")

    # Register routers
    from nfc_tv.routers.api import router as api_router
    from nfc_tv.routers.ui import router as ui_router

    app.include_router(api_router)
    app.include_router(ui_router)

    return app
