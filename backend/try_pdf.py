# Testing pdf reader

import sys
from pdf_reader import extract_slides, low_text_slides

path = sys.argv[1]            # the PDF path you type after the script name
slides = extract_slides(path)

print(f"Slides found: {len(slides)}\n")
for s in slides:
    preview = s["text"][:80].replace("\n", " ")
    print(f"Slide {s['slide']:>2} | {s['word_count']:>3} words | {preview}")

weak = low_text_slides(slides)
if weak:
    print("\nSlides with almost no text (probably images):", weak)