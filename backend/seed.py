import json
import shutil
from datetime import datetime
from pathlib import Path

from db import add_deck, add_run, db, list_decks
from pdf_reader import render_slides

ROOT = Path(__file__).parent.parent
SEED = ROOT / "seed"          # the DATA folder at the project root
DATA = ROOT / "data"
DECK_ID = "a5eed001"          # fixed ids (valid 8-character hex)
RUN_ID = "a5eed002"


def seed_if_empty():
    pdf = SEED / "demo.pdf"
    run_file = SEED / "demo_run.json"
    if list_decks() or not pdf.is_file() or not run_file.is_file():
        return
    (DATA / "decks").mkdir(parents=True, exist_ok=True)
    target = DATA / "decks" / f"{DECK_ID}.pdf"
    shutil.copy(pdf, target)
    slides = render_slides(target, DATA / "slides" / DECK_ID)

    record = json.loads(run_file.read_text(encoding="utf-8"))
    record["deck_id"], record["job_id"] = DECK_ID, RUN_ID
    add_deck(DECK_ID, "Demo deck (synthetic).pdf", len(slides))
    add_run(RUN_ID, DECK_ID, record["model"], "done", record["percent"],
            record["total_seconds"], {"note": "seeded demo run"}, None, record)
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO deck_sources (deck_id, source_url, synthetic) "
            "VALUES (?, ?, 1)", (DECK_ID, "synthetic demo deck (AI-generated)"))
        conn.execute(
            "INSERT OR REPLACE INTO links (token, deck_id, label, active, created_at) "
            "VALUES (?, ?, ?, 1, ?)",
            ("demo-viewer", DECK_ID, "Demo link",
             datetime.now().isoformat(timespec="seconds")))