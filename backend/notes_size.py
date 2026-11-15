import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
for s in data["notes"]:
    print(f"slide {s['slide']:>2}  text {len(s['text']):>4} chars  visuals {len(s['visuals']):>4} chars")