from pathlib import Path
from google.genai import types
from pydantic import BaseModel
from gemini_helper import generate_with_retry


class CriterionResult(BaseModel):
    id: str
    score: int
    slide: int            # slide number holding the evidence; 0 if the deck has nothing
    evidence: str         # short quote copied from the slide; empty if nothing found
    justification: str
    fix: str


class DeckResult(BaseModel):
    summary: str
    criteria: list[CriterionResult]


def build_prompt(rubric):
    lines = [
        "You are reviewing a startup pitch deck for an investor. "
        "Score it against the rubric below.",
        "",
        f"Scale: {rubric['scale']}",
        "Rules:",
        "- Judge only what is shown on the slides. Do not assume facts that are not shown.",
        "- 'evidence' must be ONE continuous quote copied exactly from ONE slide "
        "(under 20 words). Never use '...' and never join separate quotes. "
        "If the deck has nothing for a criterion, score it 1, set slide to 0 "
        "and leave evidence empty.",
        "- 'fix' is ONE concrete suggestion to improve that criterion.",
        "- Return exactly one entry per criterion, using the ids below.",
        "",
        "Rubric:",
    ]
    for c in rubric["criteria"]:
        lines.append(f"- id: {c['id']} | {c['name']}: {c['description']}")
        lines.append(f"    1 means: {c['low']}")
        lines.append(f"    5 means: {c['high']}")
    return "\n".join(lines)


def analyze_deck(client, model, image_paths, rubric):
    contents = [build_prompt(rubric)]
    for number, path in enumerate(image_paths, start=1):
        contents.append(f"Slide {number}:")
        contents.append(
            types.Part.from_bytes(data=Path(path).read_bytes(), mime_type="image/png")
        )

    config = types.GenerateContentConfig(
        response_mime_type="application/json",   # ask for JSON only
        response_schema=DeckResult,              # ...in exactly this shape
    )
    response = generate_with_retry(client, model, contents, config=config)
    result = DeckResult.model_validate_json(response.text)

    # Safety check: all 11 criteria, each exactly once
    expected = {c["id"] for c in rubric["criteria"]}
    got = [c.id for c in result.criteria]
    if set(got) != expected or len(got) != len(expected):
        raise ValueError(f"Model returned the wrong criteria: {got}")
    return result