import pymupdf
from pathlib import Path


def extract_slides(pdf_path):
    """
    Open a PDF and return a list with one dictionary per page (slide):
    {"slide": 1, "text": "...", "word_count": 42}
    """
    slides = []
    with pymupdf.open(pdf_path) as doc:
        for number, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            slides.append({
                "slide": number,
                "text": text,
                "word_count": len(text.split()),
            })
    return slides


def low_text_slides(slides, min_words=5):
    """Return the numbers of slides with fewer than min_words words."""
    return [s["slide"] for s in slides if s["word_count"] < min_words]


def render_slides(pdf_path, out_dir, zoom=1.0, quality=70):
    """Save every page as a JPEG image and return the list of file paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix = pymupdf.Matrix(zoom, zoom)
    paths = []
    with pymupdf.open(pdf_path) as doc:
        for number, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix)
            path = out_dir / f"slide_{number:02d}.jpg"
            pix.save(str(path), jpg_quality=quality)
            paths.append(str(path))
    return paths