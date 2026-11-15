import re
from pydantic import BaseModel
from google.genai import types
from pipeline import image_part
from pipeline_fast import call_with_deadline

FEEDBACK_TIMEOUT = 45          # seconds per attempt


class ContextIssue(BaseModel):
    problem: str
    evidence: str              # short quote from the slide text; empty if something is missing
    improvement: str


class ContextFeedback(BaseModel):
    role: str                  # rubric criterion id this slide serves, or "other"
    verdict: str
    issues: list[ContextIssue]


class ThemeIssue(BaseModel):
    problem: str
    fix: str


class ThemeFeedback(BaseModel):
    verdict: str
    issues: list[ThemeIssue]


THEME_PROMPT = (
    "You are reviewing the VISUAL DESIGN of one slide image from a startup pitch deck. "
    "Look only at design: colour contrast and readability, amount of text, size and "
    "hierarchy of headings, alignment and spacing, use of icons, charts and images, "
    "empty or placeholder elements, and whether it looks professional. "
    "Do not comment on the business content.\n"
    "Return: verdict (one sentence) and at most 3 issues, each with the problem "
    "(what you can actually see) and one concrete fix. "
    "Describe only what is visible. If the design is fine, return an empty issues list."
)


def context_prompt(notes, slide_number, rubric):
    this = next(s for s in notes if s["slide"] == slide_number)
    outline = "\n".join(f"{s['slide']}: {s['title']}" for s in notes)
    criteria = "\n".join(
        f"- {c['id']} | {c['name']}: {c['description']} Strong looks like: {c['high']}"
        for c in rubric["criteria"]
    )
    return (
        "You are reviewing ONE slide of a startup pitch deck for an investor.\n\n"
        f"Deck outline (slide number: title):\n{outline}\n\n"
        f"The slide to review (slide {slide_number}), transcribed:\n"
        f"Title: {this['title']}\nText: {this['text']}\nVisuals: {this['visuals']}\n\n"
        f"Reference rubric:\n{criteria}\n\n"
        "Return:\n"
        "- role: the rubric criterion id this slide mainly serves, or \"other\".\n"
        "- verdict: one sentence on how well the slide does its job.\n"
        "- issues: at most 3 specific problems with this slide's CONTENT (not its "
        "visual design). For each give the problem; evidence = a short exact quote "
        "from the slide text that shows it (empty if the problem is something that "
        "is missing); and one concrete improvement.\n"
        "Rules: use only what is on the slide and in the outline; do not invent facts "
        "about the company; if the slide has no real content problems, return an "
        "empty issues list."
    )


async def context_feedback(client, model, notes, slide_number, rubric):
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=ContextFeedback)
    response = await call_with_deadline(
        client, model, [context_prompt(notes, slide_number, rubric)], config,
        timeout=FEEDBACK_TIMEOUT, label=f"context {slide_number}", tries=2)
    return ContextFeedback.model_validate_json(response.text).model_dump()


async def theme_feedback(client, model, image_path, slide_number):
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=ThemeFeedback)
    response = await call_with_deadline(
        client, model, [THEME_PROMPT, image_part(image_path)], config,
        timeout=FEEDBACK_TIMEOUT, label=f"theme {slide_number}", tries=2)
    return ThemeFeedback.model_validate_json(response.text).model_dump()


class ContextRewrite(BaseModel):
    headline: str
    body: list[str]            # short lines for the slide
    placeholders: list[str]    # things the founder must supply (not invented)
    changes: str               # what changed and why


class PaletteColor(BaseModel):
    role: str                  # e.g. "background", "headline text"
    hex: str
    why: str


class ThemeRewrite(BaseModel):
    summary: str
    palette: list[PaletteColor]
    changes: list[str]


def issues_text(issues):
    lines = []
    for i in issues:
        fix = i.get("improvement") or i.get("fix") or ""
        lines.append(f"- Problem: {i['problem']} | Suggested improvement: {fix}")
    return "\n".join(lines)


def numbers_in(text):
    return set(re.findall(r"\d+(?:[.,]\d+)*", text))


async def context_rewrite(client, model, notes, slide_number, saved, rubric):
    this = next(s for s in notes if s["slide"] == slide_number)
    deck_facts = "\n\n".join(f"Slide {s['slide']} | {s['title']}\n{s['text']}" for s in notes)
    strong = next((c["high"] for c in rubric["criteria"] if c["id"] == saved.get("role")), "")
    prompt = (
        "You are rewriting ONE slide of a startup pitch deck so that it fixes the "
        "problems listed below.\n\n"
        f"Everything the deck says (transcription of every slide):\n{deck_facts}\n\n"
        f"The slide to rewrite (slide {slide_number}), as it is now:\n"
        f"Title: {this['title']}\nText: {this['text']}\n\n"
        f"What a strong slide for this role looks like: {strong or 'n/a'}\n\n"
        f"Problems found:\n{issues_text(saved['issues'])}\n\n"
        "Write the improved slide: a headline and a list of short body lines.\n"
        "Strict rules:\n"
        "- Use ONLY facts that appear somewhere in the deck transcription above. "
        "- Never narrow, widen or change the scope of a claim (for example a region "
        "or customer group). If the scope is unclear in the deck, keep the original "
        "wording and add a placeholder asking the founder to clarify.\n"
        "- Do not add sentences explaining how a figure was calculated unless the "
        "deck says so. Keep qualifiers such as 'food' or 'SEA'.\n"
        "Never invent numbers, sources, names, customers or claims.\n"
        "- Where an improvement needs information the deck does not contain "
        "(for example a source for a figure), write a bracketed placeholder such as "
        "[add source for $4.5B] in the text AND list it in placeholders.\n"
        "- Keep lines short, as investor slides do.\n"
        "- changes: one or two sentences on what you changed and why."
    )
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=ContextRewrite)
    response = await call_with_deadline(
        client, model, [prompt], config, timeout=FEEDBACK_TIMEOUT,
        label=f"context write {slide_number}", tries=2)
    result = ContextRewrite.model_validate_json(response.text).model_dump()

    # Our own check: numbers in the rewrite that appear nowhere in the deck
    new = numbers_in(" ".join([result["headline"], *result["body"]]))
    result["unverified_numbers"] = sorted(new - numbers_in(deck_facts))
    return result


async def theme_rewrite(client, model, image_path, saved):
    prompt = (
        "You are a presentation designer. Below are design problems found on this "
        "slide image. Propose concrete fixes.\n\n"
        f"Problems found:\n{issues_text(saved['issues'])}\n\n"
        "Return: summary (one sentence); palette (3 to 5 colours, each with a role, "
        "a hex code and why; stay close to the slide's existing style unless the "
        "problem is colour or contrast); changes (a list of concrete edits, each "
        "specific enough to do in PowerPoint or Google Slides).\n"
        "Rules: base the suggestions on what is visible in the image; do not "
        "redesign the whole deck."
    )
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=ThemeRewrite)
    response = await call_with_deadline(
        client, model, [prompt, image_part(image_path)], config,
        timeout=FEEDBACK_TIMEOUT, label="theme write", tries=2)
    return ThemeRewrite.model_validate_json(response.text).model_dump()


