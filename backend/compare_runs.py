import json
import sqlite3
import sys
from pathlib import Path

conn = sqlite3.connect(Path(__file__).parent.parent / "data" / "app.db")


def scores(run_id):
    row = conn.execute("SELECT result_json FROM runs WHERE id = ?", (run_id,)).fetchone()
    record = json.loads(row[0])
    return {c["id"]: c["score"] for c in record["result"]["criteria"]}


a, b = sys.argv[1], sys.argv[2]
sa, sb = scores(a), scores(b)
print(f"{'criterion':<16}{a:>10}{b:>10}")
for key in sa:
    mark = "   <-- differs" if sa[key] != sb[key] else ""
    print(f"{key:<16}{sa[key]:>10}{sb[key]:>10}{mark}")