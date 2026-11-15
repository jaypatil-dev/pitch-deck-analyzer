import json
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from analyzer import analyze_deck
from scoring import load_rubric, match_percentage

load_dotenv()
MODEL = "gemini-3.1-flash-lite"            

slides_dir = Path(sys.argv[1])
limit = int(sys.argv[2]) if len(sys.argv) > 2 else None   # optional: only first N slides
image_paths = sorted(slides_dir.glob("slide_*.png"))[:limit]
rubric = load_rubric()

total_mb = sum(p.stat().st_size for p in image_paths) / 1_000_000
print(f"Sending {len(image_paths)} slides, {total_mb:.1f} MB")

# timeout is in milliseconds: 180_000 = 180 seconds
client = genai.Client(http_options=types.HttpOptions(timeout=45_000))

start = time.time()
result = analyze_deck(client, MODEL, image_paths, rubric)
print(f"Answer received in {time.time() - start:.0f} seconds")

scores = {c.id: c.score for c in result.criteria}
percent = match_percentage(scores, rubric)

for c in result.criteria:
    print(f"{c.id:<15} {c.score}  slide {c.slide:>2} | {c.evidence[:60]}")
print(f"\nMatch: {percent}%")
print("Summary:", result.summary)

now = datetime.now()
out = {
    "deck": slides_dir.name,
    "model": MODEL,
    "slides_sent": len(image_paths),
    "time": now.isoformat(timespec="seconds"),
    "percent": percent,
    "result": result.model_dump(),
}
out_dir = Path("../data/results")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / f"{slides_dir.name}_{now:%Y%m%d_%H%M%S}.json"
out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print("Saved", out_path)