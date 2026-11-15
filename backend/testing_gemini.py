from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()                       # reads backend/.env so the key is available
MODEL = "gemini-3.6-flash"          # confirm this name in AI Studio

client = genai.Client()             # finds GEMINI_API_KEY by itself

image_bytes = Path("../data/slides/KaidoPitchDeck/slide_02.png").read_bytes()

response = client.models.generate_content(
    model=MODEL,
    contents=[
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        "This is one slide from a startup pitch deck. "
        "Quote the slide's main title and list every number it contains.",
    ],
)
print(response.text)