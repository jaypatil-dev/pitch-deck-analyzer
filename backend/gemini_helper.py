import time
import httpx
from google.genai import errors


def generate_with_retry(client, model, contents, config=None, max_tries=5):
    """Call Gemini. Retry if the server is busy (503), rate-limited (429),
    or the network connection drops."""
    wait = 5
    for attempt in range(1, max_tries + 1):
        try:
            return client.models.generate_content(
                model=model, contents=contents, config=config
            )
        except (errors.ServerError, errors.ClientError, httpx.TransportError) as e:
            code = getattr(e, "code", None)   # network errors have no status code
            retryable = isinstance(e, (errors.ServerError, httpx.TransportError)) or code == 429
            if not retryable or attempt == max_tries:
                raise
            print(f"Attempt {attempt} failed ({type(e).__name__}, code {code}). Waiting {wait}s...")
            time.sleep(wait)
            wait *= 2