import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import describe_agent
from db import (add_page_time, add_view, create_link, get_deck, get_link,
                list_files, list_links, list_views, set_link_active)

router = APIRouter()
SLIDES = Path(__file__).parent.parent / "data" / "slides"
TOKEN = re.compile(r"[A-Za-z0-9_-]{8,32}")


def valid_deck(deck_id):
    return re.fullmatch(r"[0-9a-f]{8}", deck_id) is not None and get_deck(deck_id) is not None


class NewLink(BaseModel):
    label: str


class Active(BaseModel):
    active: bool


class Ping(BaseModel):
    view_id: str
    page: int
    seconds: float


# ---------- admin endpoints (protected by the password gate in main.py) ----------

@router.get("/api/dataroom/files")
def files():
    return list_files()


@router.get("/api/decks/{deck_id}/links")
def links(deck_id: str):
    if not valid_deck(deck_id):
        raise HTTPException(status_code=404, detail="File not found")
    return list_links(deck_id)


@router.post("/api/decks/{deck_id}/links")
def new_link(deck_id: str, body: NewLink):
    if not valid_deck(deck_id):
        raise HTTPException(status_code=404, detail="File not found")
    label = body.label.strip()[:80]
    if not label:
        raise HTTPException(status_code=400,
                            detail="Give the link a label, for example the investor's name")
    return {"token": create_link(deck_id, label)}


@router.post("/api/links/{token}/active")
def link_active(token: str, body: Active):
    if not TOKEN.fullmatch(token) or not set_link_active(token, body.active):
        raise HTTPException(status_code=404, detail="Link not found")
    return {"active": body.active}


@router.get("/api/decks/{deck_id}/views")
def views(deck_id: str):
    if not valid_deck(deck_id):
        raise HTTPException(status_code=404, detail="File not found")
    return list_views(deck_id)


# ---------- public endpoints (anyone who has the link) ----------

def active_link(token):
    link = get_link(token) if TOKEN.fullmatch(token) else None
    if link is None or not link["active"]:
        raise HTTPException(status_code=404, detail="This link is not available")
    return link


@router.get("/api/view/{token}")
def view_info(token: str):
    link = active_link(token)
    return {"filename": link["filename"], "pages": link["slides"]}


@router.post("/api/view/{token}/start")
def view_start(token: str, request: Request):
    active_link(token)
    browser, os_name, device = describe_agent(request.headers.get("user-agent", ""))
    return {"view_id": add_view(token, browser, os_name, device)}


@router.get("/api/view/{token}/page/{page}")
def view_page(token: str, page: int):
    link = active_link(token)
    if not 1 <= page <= link["slides"]:
        raise HTTPException(status_code=404, detail="Page not found")
    path = SLIDES / link["deck_id"] / f"slide_{page:02d}.jpg"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/api/view/{token}/ping")
def view_ping(token: str, body: Ping):
    link = active_link(token)
    if not 1 <= body.page <= link["slides"] or not 0 < body.seconds <= 30:
        raise HTTPException(status_code=400, detail="Bad ping")
    if not add_page_time(body.view_id, token, body.page, body.seconds):
        raise HTTPException(status_code=404, detail="Unknown view")
    return {"ok": True}