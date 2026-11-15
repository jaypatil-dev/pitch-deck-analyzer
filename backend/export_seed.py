import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
run_id = sys.argv[1]
conn = sqlite3.connect(ROOT / "data" / "app.db")
row = conn.execute(
    "SELECT deck_id, result_json FROM runs WHERE id = ? AND status = 'done'",
    (run_id,)).fetchone()
if row is None:
    raise SystemExit("No finished run with that id")
(ROOT / "seed").mkdir(exist_ok=True)
(ROOT / "seed" / "demo_run.json").write_text(row[1], encoding="utf-8")
shutil.copy(ROOT / "data" / "decks" / f"{row[0]}.pdf", ROOT / "seed" / "demo.pdf")
print("Seed written to", ROOT / "seed")