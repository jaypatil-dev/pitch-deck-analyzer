import sys
from pathlib import Path
from pdf_reader import render_slides

pdf = Path(sys.argv[1])
out = Path("../data/slides") / pdf.stem
paths = render_slides(pdf, out, zoom=1.0)
mb = sum(Path(p).stat().st_size for p in paths) / 1_000_000
print(f"Saved {len(paths)} images ({mb:.1f} MB total) to {out}")