"""HTML page routes."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@router.get("/cards")
def cards_page(request: Request):
    state = request.app.state.app_state
    cards = state.config.get("cards", {})
    card_list = [{"uid": uid, **data} for uid, data in cards.items()]
    return templates.TemplateResponse(request, "cards.html", {"cards": card_list})


@router.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")
