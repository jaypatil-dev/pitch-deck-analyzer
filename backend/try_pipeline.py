import json
import sys
import time
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pipeline import quote_found
from pipeline_fast import analyze_deck_fast
from scoring import load_rubric, match_percentage

load_dotenv()
MODEL = "gemini-3.1-flash-lite"

slides_dir = Path(sys.argv[1])
batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 3
image_paths = sorted(slides_dir.glob("slide_*.jpg"))
rubric = load_rubric()
mb = sum(p.stat().st_size for p in image_paths) / 1_000_000
print(f"{len(image_paths)} slides, {mb:.1f} MB, batch size {batch_size}, model {MODEL}")

client = genai.Client(http_options=types.HttpOptions(timeout=60_000))

start = time.time()
notes, result = asyncio.run(analyze_deck_fast(client, MODEL, image_paths, rubric, batch_size))
total = time.time() - start
print(f"Total time: {total:.0f} s\n")

scores = {c.id: c.score for c in result.criteria}
percent = match_percentage(scores, rubric)
for c in result.criteria:
    found = quote_found(c, notes)
    mark = {True: "found", False: "NOT FOUND", None: "no quote"}[found]
    print(f"{c.id:<15} {c.score}  slide {c.slide:>2} | {mark:<9} | {c.evidence[:50]}")
print(f"\nMatch: {percent}%")
print("Summary:", result.summary)

now = datetime.now()
out = {
    "deck": slides_dir.name,
    "model": MODEL,
    "batch_size": batch_size,
    "total_seconds": round(total),
    "time": now.isoformat(timespec="seconds"),
    "percent": percent,
    "mode": "parallel, 1 slide per call, prompt v2",
    "notes": [s.model_dump() for s in notes],
    "result": result.model_dump(),
}
out_dir = Path("../data/results")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f"{slides_dir.name}_b{batch_size}_{now:%Y%m%d_%H%M%S}.json"
out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print("Saved", out_path)