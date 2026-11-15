import sqlite3
from pathlib import Path

conn = sqlite3.connect(Path(__file__).parent.parent / "data" / "app.db")

print("DECKS")
for row in conn.execute("SELECT id, filename, slides, uploaded_at FROM decks"):
    print("  ", row)

print("RUNS")
for row in conn.execute(
    "SELECT id, deck_id, status, percent, total_seconds, model, saved_at FROM runs"
):
    print("  ", row)