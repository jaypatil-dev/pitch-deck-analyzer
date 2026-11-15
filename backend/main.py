import asyncio
import re
import uuid
import hashlib
import hmac
import os
import time
import traceback
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, Request
from db import add_deck, get_deck, get_run, init_db, list_all_runs, list_decks, list_runs, save_feedback, get_feedback, save_human_scores
from jobs import JOBS, MODEL, LIBRARY_TIMEOUT_MS, create_job, run_analysis
from pdf_reader import render_slides
from scoring import load_rubric
from fastapi.responses import FileResponse, JSONResponse
from google import genai
from google.genai import types
from feedback import context_feedback, context_rewrite, theme_feedback, theme_rewrite
from pydantic import BaseModel
from evaluation import evaluate
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from dataroom import router as dataroom_router
from seed import seed_if_empty

load_dotenv()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

app = FastAPI(title="Pitch Deck Analyzer")
init_db()

seed_if_empty()
app.include_router(dataroom_router)

DATA = Path(__file__).parent.parent / "data"
DECKS = DATA / "decks"
SLIDES = DATA / "slides"
MAX_MB = 25
def valid_id(value):
    """Ids we create are exactly 8 hex characters. Reject anything else."""
    return re.fullmatch(r"[0-9a-f]{8}", value) is not None

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/decks")
def upload_deck(file: UploadFile):
    content = file.file.read()
    if len(content) > MAX_MB * 1_000_000:
        raise HTTPException(status_code=413, detail=f"File is larger than {MAX_MB} MB")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="This file is not a PDF")

    deck_id = uuid.uuid4().hex[:8]            # random id, e.g. "a3f9c21b"
    DECKS.mkdir(parents=True, exist_ok=True)
    pdf_path = DECKS / f"{deck_id}.pdf"
    pdf_path.write_bytes(content)

    try:
        slide_paths = render_slides(pdf_path, SLIDES / deck_id)
    except Exception:
        pdf_path.unlink(missing_ok=True)      # remove the broken upload
        raise HTTPException(status_code=400, detail="Could not read this PDF")

    add_deck(deck_id, (file.filename or "deck.pdf")[:200], len(slide_paths))

    return {"deck_id": deck_id, "filename": file.filename, "slides": len(slide_paths)}


RUNNING = set()   # keeps background tasks alive until they finish


@app.post("/api/decks/{deck_id}/analyze")
async def start_analysis(deck_id: str):
    slide_dir = SLIDES / deck_id
    # deck_id must look exactly like one we created (8 hex characters)
    if not re.fullmatch(r"[0-9a-f]{8}", deck_id) or not slide_dir.is_dir():
        raise HTTPException(status_code=404, detail="Deck not found")

    slide_count = len(list(slide_dir.glob("slide_*.jpg")))
    job_id = create_job(deck_id, slide_count)

    task = asyncio.create_task(run_analysis(job_id))   # start it, don't wait for it
    RUNNING.add(task)
    task.add_done_callback(RUNNING.discard)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/decks")
def decks():
    return list_decks()


@app.get("/api/decks/{deck_id}/runs")
def deck_runs(deck_id: str):
    if not valid_id(deck_id) or get_deck(deck_id) is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    return list_runs(deck_id)


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    found = get_run(run_id) if valid_id(run_id) else None
    if found is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return found

@app.get("/api/rubric")
def rubric():
    return load_rubric()


@app.get("/api/runs")
def all_runs():
    return list_all_runs()


@app.get("/api/decks/{deck_id}/slides/{slide}")
def slide_image(deck_id: str, slide: int):
    path = SLIDES / deck_id / f"slide_{slide:02d}.jpg" if valid_id(deck_id) else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Slide image not found")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/runs/{run_id}/feedback")
def run_feedback(run_id: str):
    if not valid_id(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return get_feedback(run_id)


KINDS = ("context", "theme", "context_write", "theme_write")


@app.post("/api/runs/{run_id}/slides/{slide}/{kind}")
async def make_feedback(run_id: str, slide: int, kind: str):
    found = get_run(run_id) if valid_id(run_id) else None
    if found is None or found["status"] != "done":
        raise HTTPException(status_code=404, detail="Run not found")
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail="Unknown kind")
    notes = found["result"]["notes"]
    if not 1 <= slide <= len(notes):
        raise HTTPException(status_code=404, detail="Slide not found")

    saved = None
    if kind.endswith("_write"):
        base = kind.removesuffix("_write")
        saved = get_feedback(run_id).get(str(slide), {}).get(base)
        if saved is None:
            raise HTTPException(status_code=400, detail="Run the check for this slide first")
        if not saved["issues"]:
            raise HTTPException(status_code=400, detail="No problems to fix on this slide")

    client = genai.Client(http_options=types.HttpOptions(timeout=LIBRARY_TIMEOUT_MS))
    try:
        if kind == "context":
            result = await context_feedback(client, MODEL, notes, slide, load_rubric())
        elif kind == "context_write":
            result = await context_rewrite(client, MODEL, notes, slide, saved, load_rubric())
        else:
            image = SLIDES / found["deck_id"] / f"slide_{slide:02d}.jpg"
            if not image.is_file():
                raise HTTPException(status_code=404, detail="Slide image not found")
            if kind == "theme":
                result = await theme_feedback(client, MODEL, image, slide)
            else:
                result = await theme_rewrite(client, MODEL, image, saved)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Model call failed ({type(e).__name__})")

    save_feedback(run_id, slide, kind, MODEL, result)
    return result

#Login/Logout Section
PUBLIC_PREFIXES = ("/api/view/", "/api/health", "/api/session", "/api/login", "/api/logout")


def admin_token():
    return hmac.new(ADMIN_PASSWORD.encode(), b"admin-session", hashlib.sha256).hexdigest()


def is_admin(request: Request):
    if not ADMIN_PASSWORD:
        return True                         # no password set: local development
    cookie = request.cookies.get("admin", "")
    return hmac.compare_digest(cookie.encode(), admin_token().encode())


@app.middleware("http")
async def admin_gate(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not path.startswith(PUBLIC_PREFIXES) \
            and not is_admin(request):
        return JSONResponse({"detail": "Admin password required"}, status_code=401)
    return await call_next(request)


class Login(BaseModel):
    password: str


@app.get("/api/session")
def session(request: Request):
    return {"required": bool(ADMIN_PASSWORD), "authenticated": is_admin(request)}


@app.post("/api/login")
def login(body: Login, request: Request):
    if ADMIN_PASSWORD and not hmac.compare_digest(
            body.password.encode(), ADMIN_PASSWORD.encode()):
        time.sleep(1)                       # slows down password guessing
        raise HTTPException(status_code=401, detail="Wrong password")
    response = JSONResponse({"ok": True})
    if ADMIN_PASSWORD:
        response.set_cookie(
            "admin", admin_token(), httponly=True, samesite="lax", max_age=8 * 3600,
            secure=request.headers.get("x-forwarded-proto") == "https")
    return response

@app.post("/api/logout")
def logout(request: Request):
    response = JSONResponse({"ok": True})
    response.delete_cookie(
        "admin", httponly=True, samesite="lax",
        secure=request.headers.get("x-forwarded-proto") == "https")
    return response





class HumanScores(BaseModel):
    scores: dict[str, int]
    source_url: str = ""
    synthetic: bool = False


@app.post("/api/decks/{deck_id}/human-scores")
def human_scores(deck_id: str, body: HumanScores):
    if not valid_id(deck_id) or get_deck(deck_id) is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    ids = {c["id"] for c in load_rubric()["criteria"]}
    if set(body.scores) != ids or not all(1 <= v <= 5 for v in body.scores.values()):
        raise HTTPException(status_code=400, detail="Give a score from 1 to 5 for every criterion")
    url = body.source_url.strip()
    if not body.synthetic and not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Enter the public URL where this deck was published")
    save_human_scores(deck_id, body.scores, url, body.synthetic)
    return {"saved": True}


@app.get("/api/evaluation")
def evaluation():
    return evaluate()



DIST = Path(__file__).parent.parent / "frontend" / "dist"

if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (DIST / full_path).resolve()
        if full_path and candidate.is_file() and DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")


    