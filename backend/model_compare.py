import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from analyzer import build_prompt, DeckResult
from scoring import load_rubric

load_dotenv()

client = genai.Client(http_options=types.HttpOptions(
    timeout=60_000,                                    # 60 seconds
    retry_options=types.HttpRetryOptions(attempts=1),  # no hidden retries
))
rubric = load_rubric()
slide = types.Part.from_bytes(
    data=Path("../data/slides/KaidoPitchDeck/slide_02.png").read_bytes(),
    mime_type="image/png",
)
contents = [build_prompt(rubric), "Slide 2:", slide]
config = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=DeckResult,
)

for model in sys.argv[1:]:                  # model names typed after the script name
    for trial in (1, 2):
        start = time.time()
        try:
            client.models.generate_content(model=model, contents=contents, config=config)
            print(f"{model:<28} trial {trial}  OK    {time.time() - start:5.1f} s")
        except Exception as e:
            print(f"{model:<28} trial {trial}  FAIL  {time.time() - start:5.1f} s  {type(e).__name__}")