import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from analyzer import build_prompt, DeckResult
from scoring import load_rubric

load_dotenv()
MODEL = "gemini-3.6-flash"

# 45-second limit (milliseconds), and only one attempt: no hidden retries
client = genai.Client(http_options=types.HttpOptions(
    timeout=45_000,
    retry_options=types.HttpRetryOptions(attempts=1),
))
rubric = load_rubric()
folder = Path("../data/slides/KaidoPitchDeck")
imgs = [
    types.Part.from_bytes(data=(folder / f"slide_{n:02d}.png").read_bytes(),
                          mime_type="image/png")
    for n in (1, 2, 3)
]


def run(name, contents, config=None):
    start = time.time()
    try:
        client.models.generate_content(model=MODEL, contents=contents, config=config)
        print(f"{name:<46} OK    {time.time() - start:5.1f} s")
    except Exception as e:
        print(f"{name:<46} FAIL  {time.time() - start:5.1f} s  {type(e).__name__}")


low = types.ThinkingConfig(thinking_level="low")
json_low = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=DeckResult,
    thinking_config=low,
)
ask = "Quote this slide's main title."

run("A: 1 slide, simple question, default thinking", [imgs[1], ask])
run("B: 1 slide, simple question, thinking low",
    [imgs[1], ask], types.GenerateContentConfig(thinking_config=low))
run("C: 1 slide, rubric + JSON, thinking low",
    [build_prompt(rubric), "Slide 2:", imgs[1]], json_low)
run("D: 3 slides, rubric + JSON, thinking low",
    [build_prompt(rubric), "Slide 1:", imgs[0], "Slide 2:", imgs[1],
     "Slide 3:", imgs[2]], json_low)