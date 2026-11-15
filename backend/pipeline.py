import time
import re
from pathlib import Path
from google.genai import types
from pydantic import BaseModel
from analyzer import DeckResult, build_prompt
from gemini_helper import generate_with_retry


class SlideNotes(BaseModel):
    slide: int
    title: str
    text: str       # all visible text on the slide, copied as written
    visuals: str    # short description of charts, images, icons, layout


class BatchNotes(BaseModel):
    slides: list[SlideNotes]


def image_part(path):
    path = Path(path)
    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)


def extract_batch(client, model, numbered_paths):
    """numbered_paths: list of (slide_number, image_path). Returns a list of SlideNotes."""
    contents = [
        "Below are slides from a startup pitch deck. For each slide, copy ALL visible "
        "text exactly as written, give its title, and briefly describe any charts, "
        "images or icons. Do not judge the slide or add anything that is not on it."
    ]
    for number, path in numbered_paths:
        contents.append(f"Slide {number}:")
        contents.append(image_part(path))

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=BatchNotes,
    )
    response = generate_with_retry(client, model, contents, config=config)
    notes = BatchNotes.model_validate_json(response.text).slides

    expected = {number for number, _ in numbered_paths}
    got = {s.slide for s in notes}
    if got != expected:
        raise ValueError(f"Expected slides {sorted(expected)}, got {sorted(got)}")
    return notes


def score_from_notes(client, model, notes, rubric):
    deck_text = "\n\n".join(
        f"Slide {s.slide} | {s.title}\n{s.text}\nVisuals: {s.visuals}" for s in notes
    )
    prompt = (build_prompt(rubric)
              + "\n\nHere are all the slides of the deck, as transcribed:\n\n" + deck_text)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=DeckResult,
    )
    response = generate_with_retry(client, model, [prompt], config=config)
    result = DeckResult.model_validate_json(response.text)

    expected = {c["id"] for c in rubric["criteria"]}
    got = [c.id for c in result.criteria]
    if set(got) != expected or len(got) != len(expected):
        raise ValueError(f"Model returned the wrong criteria: {got}")
    return result





def _clean(text):
    text = text.lower()
    for a, b in (("–", "-"), ("—", "-"), ("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(a, b)
    return " ".join(text.split())


def quote_found(criterion, notes):
    """True if every fragment of the quote is in that slide's notes; None if no quote."""
    if not criterion.evidence:
        return None
    slide_text = {s.slide: _clean(s.title + " " + s.text) for s in notes}.get(criterion.slide, "")
    fragments = re.split(r"\.\.\.|…|;", _clean(criterion.evidence))
    fragments = [f.strip(" .,:;") for f in fragments if f.strip(" .,:;")]
    return all(f in slide_text for f in fragments)



def analyze_deck_batched(client, model, image_paths, rubric, batch_size=3):
    numbered = list(enumerate(image_paths, start=1))
    notes = []
    for i in range(0, len(numbered), batch_size):
        batch = numbered[i:i + batch_size]
        start = time.time()
        notes.extend(extract_batch(client, model, batch))
        print(f"  slides {batch[0][0]}-{batch[-1][0]} read in {time.time() - start:.1f} s")
    notes.sort(key=lambda s: s.slide)

    start = time.time()
    result = score_from_notes(client, model, notes, rubric)
    print(f"  scoring done in {time.time() - start:.1f} s")
    return notes, result