import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pipeline import image_part
from pipeline_fast import READ_PROMPT

load_dotenv()
MODEL = "gemini-3.1-flash-lite"
client = genai.Client()
slide = image_part(Path("../data/slides/KaidoPitchDeck/slide_02.jpg"))


async def one(i):
    start = time.time()
    try:
        await asyncio.wait_for(
            client.aio.models.generate_content(
                model=MODEL, contents=[READ_PROMPT, slide]),
            timeout=45,
        )
        return time.time() - start
    except Exception as e:
        return f"FAIL {type(e).__name__}"


async def main():
    t0 = time.time()
    results = await asyncio.gather(*[one(i) for i in range(4)])
    total = time.time() - t0
    print("Individual times:", [r if isinstance(r, str) else round(r, 1) for r in results])
    print(f"Total: {total:.1f} s")


asyncio.run(main())