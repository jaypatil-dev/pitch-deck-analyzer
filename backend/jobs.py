import json
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pipeline import quote_found
from pipeline_fast import analyze_deck_fast
from scoring import load_rubric, match_percentage
from db import add_run

load_dotenv()
MODEL = "gemini-3.1-flash-lite"
READ_TIMEOUT = 75            # seconds before one slide read is cancelled and retried
SCORE_TIMEOUT = 90           # seconds for the scoring call
LIBRARY_TIMEOUT_MS = 120_000 # backstop inside the Google library, in MILLISECONDS
SETTINGS = {
    "mode": "parallel, 1 slide per call",
    "prompt": "v2",
    "read_timeout_s": READ_TIMEOUT,
    "score_timeout_s": SCORE_TIMEOUT,
    "library_timeout_ms": LIBRARY_TIMEOUT_MS,
}
DATA = Path(__file__).parent.parent / "data"
SLIDES = DATA / "slides"
RESULTS = DATA / "results"

JOBS = {}      # job_id -> dict with that job's progress (kept in memory)


def create_job(deck_id, slide_count):
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {
        "job_id": job_id,
        "deck_id": deck_id,
        "status": "queued",            # queued -> reading -> scoring -> done / failed
        "slides_total": slide_count,
        "slides_done": 0,
        "slide_timeline": {},          # slide number -> {"start": s, "end": s}
        "error": None,
        "result": None,
    }
    return job_id


async def run_analysis(job_id):
    job = JOBS[job_id]
    t0 = time.time()

    def progress(event, **info):
        if event == "slide_read":
            job["slides_done"] += 1
            job["slide_timeline"][info["number"]] = {
                "start": round(info["started"] - t0, 1),
                "end": round(info["finished"] - t0, 1),
            }
        elif event == "scoring":
            job["status"] = "scoring"

    try:
        rubric = load_rubric()
        image_paths = sorted((SLIDES / job["deck_id"]).glob("slide_*.jpg"))
        client = genai.Client(http_options=types.HttpOptions(timeout=LIBRARY_TIMEOUT_MS))

        job["status"] = "reading"
        notes, result = await analyze_deck_fast(
            client, MODEL, image_paths, rubric, progress=progress,read_timeout=READ_TIMEOUT, score_timeout=SCORE_TIMEOUT)

        scores = {c.id: c.score for c in result.criteria}
        record = {
            "deck_id": job["deck_id"],
            "job_id": job_id,
            "model": MODEL,
            "mode": "parallel, 1 slide per call, prompt v2",
            "time": datetime.now().isoformat(timespec="seconds"),
            "total_seconds": round(time.time() - t0),
            "slide_timeline": job["slide_timeline"],
            "percent": match_percentage(scores, rubric),
            "quote_checks": {c.id: quote_found(c, notes) for c in result.criteria},
            "notes": [s.model_dump() for s in notes],
            "result": result.model_dump(),
            "read_timeout": READ_TIMEOUT,
            "score_timeout": SCORE_TIMEOUT,
            "library_timeout": LIBRARY_TIMEOUT_MS,
        }
        RESULTS.mkdir(parents=True, exist_ok=True)
        path = RESULTS / f"{job['deck_id']}_{job_id}.json"
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")

        add_run(
            run_id=job_id, deck_id=job["deck_id"], model=MODEL, status="done",
            percent=record["percent"], total_seconds=record["total_seconds"],
            settings=SETTINGS, error=None, result=record,
        )

        job["result"] = record
        job["status"] = "done"
    except Exception as e:
        traceback.print_exc()
        job["status"] = "failed"
        job["error"] = f"{type(e).__name__} (code {getattr(e, 'code', None)})"
        RESULTS.mkdir(parents=True, exist_ok=True)
        failure = {
            "deck_id": job["deck_id"],
            "job_id": job_id,
            "model": MODEL,
            "time": datetime.now().isoformat(timespec="seconds"),
            "error": job["error"],
            "slides_done": job["slides_done"],
            "slide_timeline": job["slide_timeline"],
        }
        (RESULTS / f"FAILED_{job['deck_id']}_{job_id}.json").write_text(
            json.dumps(failure, indent=2), encoding="utf-8")
        add_run(
            run_id=job_id, deck_id=job["deck_id"], model=MODEL, status="failed",
            percent=None, total_seconds=round(time.time() - t0),
            settings=SETTINGS, error=job["error"], result=failure,
        )