import json
import sqlite3
import secrets
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "app.db"


@contextmanager
def db():
    """Open the database, save changes if all went well, undo them if not, always close."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows can be turned into dictionaries
    try:
        yield conn
        conn.commit()                       # keep the changes
    except Exception:
        conn.rollback()                     # undo a half-finished change
        raise
    finally:
        conn.close()


def init_db():
    """Create the tables the first time. Safe to run every time the server starts."""
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS decks (
                id          TEXT PRIMARY KEY,
                filename    TEXT NOT NULL,
                slides      INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id            TEXT PRIMARY KEY,
                deck_id       TEXT NOT NULL REFERENCES decks(id),
                saved_at      TEXT NOT NULL,
                model         TEXT NOT NULL,
                status        TEXT NOT NULL,     -- done or failed
                percent       REAL,
                total_seconds INTEGER,
                settings      TEXT,              -- JSON text
                error         TEXT,
                result_json   TEXT               -- the whole result, as JSON text
            );
            CREATE TABLE IF NOT EXISTS slide_feedback (
                run_id      TEXT NOT NULL REFERENCES runs(id),
                slide       INTEGER NOT NULL,
                kind        TEXT NOT NULL,       -- context or theme
                created_at  TEXT NOT NULL,
                model       TEXT NOT NULL,
                result_json TEXT NOT NULL,
                PRIMARY KEY (run_id, slide, kind)
            );
            CREATE TABLE IF NOT EXISTS human_scores (
                deck_id   TEXT NOT NULL REFERENCES decks(id),
                criterion TEXT NOT NULL,
                score     INTEGER NOT NULL,
                scored_at TEXT NOT NULL,
                PRIMARY KEY (deck_id, criterion)
            );
            CREATE TABLE IF NOT EXISTS deck_sources (
                deck_id    TEXT PRIMARY KEY REFERENCES decks(id),
                source_url TEXT NOT NULL,
                synthetic  INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS links (
                token      TEXT PRIMARY KEY,
                deck_id    TEXT NOT NULL REFERENCES decks(id),
                label      TEXT NOT NULL,
                active     INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS views (
                id         TEXT PRIMARY KEY,
                token      TEXT NOT NULL REFERENCES links(token),
                started_at TEXT NOT NULL,
                last_seen  TEXT NOT NULL,
                browser    TEXT,
                os         TEXT,
                device     TEXT
            );
            CREATE TABLE IF NOT EXISTS view_pages (
                view_id TEXT NOT NULL REFERENCES views(id),
                page    INTEGER NOT NULL,
                seconds REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (view_id, page)
            );
        """)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def add_deck(deck_id, filename, slides):
    with db() as conn:
        conn.execute(
            "INSERT INTO decks (id, filename, slides, uploaded_at) VALUES (?, ?, ?, ?)",
            (deck_id, filename, slides, _now()),
        )


def list_decks():
    with db() as conn:
        rows = conn.execute("""
            SELECT d.*,
                   (SELECT COUNT(*) FROM runs r WHERE r.deck_id = d.id) AS runs,
                   (SELECT COUNT(*) FROM human_scores h WHERE h.deck_id = d.id) AS human_scored
            FROM decks d ORDER BY d.uploaded_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_deck(deck_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
    return dict(row) if row else None


def add_run(run_id, deck_id, model, status, percent, total_seconds,
            settings, error, result):
    with db() as conn:
        conn.execute(
            """INSERT INTO runs (id, deck_id, saved_at, model, status, percent,
                                 total_seconds, settings, error, result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, deck_id, _now(), model, status, percent, total_seconds,
             json.dumps(settings), error,
             json.dumps(result) if result is not None else None),
        )


def list_runs(deck_id):
    with db() as conn:
        rows = conn.execute(
            """SELECT id, saved_at, model, status, percent, total_seconds, error
               FROM runs WHERE deck_id = ? ORDER BY saved_at DESC""",
            (deck_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id):
    with db() as conn:
        row = conn.execute(
            "SELECT r.*, d.filename FROM runs r JOIN decks d ON d.id = r.deck_id "
            "WHERE r.id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    run = dict(row)
    result_json = run.pop("result_json")
    run["result"] = json.loads(result_json) if result_json else None
    run["settings"] = json.loads(run["settings"]) if run["settings"] else None
    return run

def list_all_runs():
    with db() as conn:
        rows = conn.execute("""
            SELECT r.id, r.saved_at, r.model, r.status, r.percent,
                   r.total_seconds, r.error, d.filename
            FROM runs r JOIN decks d ON d.id = r.deck_id
            ORDER BY r.saved_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def save_feedback(run_id, slide, kind, model, result):
    with db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO slide_feedback
               (run_id, slide, kind, created_at, model, result_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, slide, kind, _now(), model, json.dumps(result)),
        )


def get_feedback(run_id):
    """Return {"3": {"context": {...}, "theme": {...}}, ...} for one run."""
    with db() as conn:
        rows = conn.execute(
            """SELECT slide, kind, model, created_at, result_json
               FROM slide_feedback WHERE run_id = ?""",
            (run_id,),
        ).fetchall()
    out = {}
    for r in rows:
        entry = {"model": r["model"], "created_at": r["created_at"]}
        entry.update(json.loads(r["result_json"]))
        out.setdefault(str(r["slide"]), {})[r["kind"]] = entry
    return out



def save_human_scores(deck_id, scores, source_url, synthetic):
    with db() as conn:
        for criterion, score in scores.items():
            conn.execute(
                "INSERT OR REPLACE INTO human_scores (deck_id, criterion, score, scored_at) "
                "VALUES (?, ?, ?, ?)",
                (deck_id, criterion, score, _now()),
            )
        conn.execute(
            "INSERT OR REPLACE INTO deck_sources (deck_id, source_url, synthetic) "
            "VALUES (?, ?, ?)",
            (deck_id, source_url, 1 if synthetic else 0),
        )

def list_files():
    with db() as conn:
        rows = conn.execute("""
            SELECT d.id, d.filename, d.slides, d.uploaded_at,
                   (SELECT COUNT(*) FROM links l WHERE l.deck_id = d.id) AS links,
                   (SELECT COUNT(*) FROM views v JOIN links l ON l.token = v.token
                     WHERE l.deck_id = d.id) AS views
            FROM decks d ORDER BY d.uploaded_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def create_link(deck_id, label):
    token = secrets.token_urlsafe(9)          # 12 URL-safe characters, unguessable
    with db() as conn:
        conn.execute(
            "INSERT INTO links (token, deck_id, label, active, created_at) "
            "VALUES (?, ?, ?, 1, ?)", (token, deck_id, label, _now()))
    return token


def list_links(deck_id):
    with db() as conn:
        rows = conn.execute("""
            SELECT l.token, l.label, l.active, l.created_at,
                   (SELECT COUNT(*) FROM views v WHERE v.token = l.token) AS views
            FROM links l WHERE l.deck_id = ? ORDER BY l.created_at DESC
        """, (deck_id,)).fetchall()
    return [dict(r) for r in rows]


def set_link_active(token, active):
    with db() as conn:
        cur = conn.execute("UPDATE links SET active = ? WHERE token = ?",
                           (1 if active else 0, token))
    return cur.rowcount > 0


def get_link(token):
    with db() as conn:
        row = conn.execute("""
            SELECT l.token, l.deck_id, l.label, l.active, d.filename, d.slides
            FROM links l JOIN decks d ON d.id = l.deck_id WHERE l.token = ?
        """, (token,)).fetchone()
    return dict(row) if row else None


def add_view(token, browser, os_name, device):
    view_id = secrets.token_urlsafe(12)
    now = _now()
    with db() as conn:
        conn.execute(
            "INSERT INTO views (id, token, started_at, last_seen, browser, os, device) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (view_id, token, now, now, browser, os_name, device))
    return view_id


def add_page_time(view_id, token, page, seconds):
    """Add seconds to one page of one view. False if the view is unknown."""
    with db() as conn:
        known = conn.execute("SELECT 1 FROM views WHERE id = ? AND token = ?",
                             (view_id, token)).fetchone()
        if not known:
            return False
        conn.execute("""
            INSERT INTO view_pages (view_id, page, seconds) VALUES (?, ?, ?)
            ON CONFLICT(view_id, page) DO UPDATE SET seconds = seconds + excluded.seconds
        """, (view_id, page, seconds))
        conn.execute("UPDATE views SET last_seen = ? WHERE id = ?", (_now(), view_id))
    return True


def list_views(deck_id):
    with db() as conn:
        views = conn.execute("""
            SELECT v.id, v.started_at, v.last_seen, v.browser, v.os, v.device, l.label
            FROM views v JOIN links l ON l.token = v.token
            WHERE l.deck_id = ? ORDER BY v.started_at DESC
        """, (deck_id,)).fetchall()
        out = []
        for v in views:
            pages = conn.execute(
                "SELECT page, seconds FROM view_pages WHERE view_id = ? ORDER BY page",
                (v["id"],)).fetchall()
            item = dict(v)
            item.pop("id")                          # the ping secret never leaves the server
            item["pages"] = [{"page": p["page"], "seconds": round(p["seconds"])} for p in pages]
            item["total_seconds"] = round(sum(p["seconds"] for p in pages))
            out.append(item)
    return out