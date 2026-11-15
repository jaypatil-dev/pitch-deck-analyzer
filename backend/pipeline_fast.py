import asyncio
import time
from collections import deque

import httpx
from google.genai import errors, types

from analyzer import DeckResult, build_prompt
from pipeline import BatchNotes, image_part

READ_PROMPT = (
    "Below is one slide from a startup pitch deck. Copy ALL visible text exactly as "
    "written, give its title, and briefly describe any charts, images or icons. "
    "Do not judge the slide or add anything that is not on it."
)


class RateLimiter:
    """Allow at most max_calls requests in any rolling window of `window` seconds."""

    def __init__(self, max_calls, window=60):
        self.max_calls = max_calls
        self.window = window
        self.sent = deque()              # times of the recent requests
        self.lock = asyncio.Lock()

    async def wait(self):
        while True:
            async with self.lock:
                now = time.monotonic()
                while self.sent and now - self.sent[0] >= self.window:
                    self.sent.popleft()            # forget requests older than the window
                if len(self.sent) < self.max_calls:
                    self.sent.append(now)          # take a slot and go
                    return
                delay = self.window - (now - self.sent[0])
            await asyncio.sleep(delay + 0.05)      # wait until the oldest one expires


# The free tier allows 15 requests per minute for gemini-3.1-flash-lite.
# 14 leaves a margin of 1. If you still see 429 errors, lower it to 12.
LIMITER = RateLimiter(max_calls=14, window=60)


def is_retryable(e):
    """Retry only problems that can go away: timeouts, network drops, server
    errors and rate limits (429). Other 4xx errors never will."""
    if isinstance(e, (asyncio.TimeoutError, httpx.TransportError, errors.ServerError)):
        return True
    return isinstance(e, errors.ClientError) and e.code == 429


async def call_with_deadline(client, model, contents, config, timeout, label, tries=3):
    """One request with a hard time limit. Retry only when it makes sense."""
    for attempt in range(1, tries + 1):
        await LIMITER.wait()                       # wait for a free request slot
        start = time.time()
        try:
            return await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model, contents=contents, config=config),
                timeout=timeout,
            )
        except Exception as e:
            code = getattr(e, "code", None)
            print(f"  {label}: attempt {attempt} failed "
                  f"({type(e).__name__}, code {code}) after {time.time() - start:.0f} s")
            if attempt == tries or not is_retryable(e):
                raise
            await asyncio.sleep(25 if code == 429 else 1)   # Google said "retry in ~22 s"


async def read_slide(client, model, number, path, gate, timeout, progress=None):
    contents = [READ_PROMPT, f"Slide {number}:", image_part(path)]
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=BatchNotes)
    async with gate:                                 # wait for a free slot (not timed)
        started = time.time()
        response = await call_with_deadline(
            client, model, contents, config, timeout, f"slide {number}")
    notes = BatchNotes.model_validate_json(response.text).slides
    if len(notes) != 1 or notes[0].slide != number:
        raise ValueError(f"Slide {number}: unexpected reply")
    finished = time.time()
    print(f"  slide {number} read in {finished - started:.1f} s")
    if progress:
        progress("slide_read", number=number, started=started, finished=finished)
    return notes[0]


async def score_deck(client, model, notes, rubric, timeout):
    deck_text = "\n\n".join(
        f"Slide {s.slide} | {s.title}\n{s.text}\nVisuals: {s.visuals}" for s in notes)
    prompt = (build_prompt(rubric)
              + "\n\nHere are all the slides of the deck, as transcribed:\n\n" + deck_text)
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=DeckResult)
    response = await call_with_deadline(
        client, model, [prompt], config, timeout, "scoring")
    result = DeckResult.model_validate_json(response.text)

    expected = {c["id"] for c in rubric["criteria"]}
    got = [c.id for c in result.criteria]
    if set(got) != expected or len(got) != len(expected):
        raise ValueError(f"Model returned the wrong criteria: {got}")
    return result


async def analyze_deck_fast(client, model, image_paths, rubric,
                            max_parallel=4, read_timeout=45, score_timeout=45,
                            progress=None):
    gate = asyncio.Semaphore(max_parallel)           # at most 4 requests at once
    start = time.time()
    tasks = [asyncio.create_task(
                 read_slide(client, model, n, p, gate, read_timeout, progress))
             for n, p in enumerate(image_paths, start=1)]
    try:
        notes = await asyncio.gather(*tasks)
    except BaseException:
        for t in tasks:
            t.cancel()                 # stop the other slides if one has failed
        raise
    print(f"  all slides read in {time.time() - start:.1f} s")
    notes = sorted(notes, key=lambda s: s.slide)

    if progress:
        progress("scoring")
    start = time.time()
    result = await score_deck(client, model, notes, rubric, score_timeout)
    print(f"  scoring done in {time.time() - start:.1f} s")
    return notes, result