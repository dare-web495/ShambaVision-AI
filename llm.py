import io
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

MODEL = os.getenv("MODEL", "gemma-4-26b-a4b-it")
SYSTEM_PROMPT = Path("prompts", "system.txt").read_text(encoding="utf-8")

_client = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _client


def prepare_image(image_bytes, max_side=1024):
    """Shrink the photo so uploads and responses are faster."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def extract_json(text):
    """Pull the JSON object out of the reply, even if it has extra text or code fences."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise json.JSONDecodeError("No JSON found", text, 0)
    return json.loads(match.group(0))


def diagnose(image_bytes, crop, language, reference):
    if not os.getenv("GOOGLE_API_KEY"):
        return {"error": "GOOGLE_API_KEY is missing. Check your .env file."}

    prompt = (
        SYSTEM_PROMPT
        + "\n\n"
        + f"Crop (may be 'Unknown'): {crop}\n"
        + f"Reply language: {language}\n"
        + f"REFERENCE DATA:\n{json.dumps(reference, ensure_ascii=False)}\n"
        + "Diagnose the plant in the photo. Reply with the JSON only."
    )
    try:
        response = get_client().models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(
                    data=prepare_image(image_bytes), mime_type="image/jpeg"
                ),
                prompt,
            ],
            config=types.GenerateContentConfig(temperature=0.2),
        )
        return extract_json(response.text)
    except json.JSONDecodeError:
        return {"error": "The model gave an unreadable answer. Please try again."}
    except Exception as e:
        return {"error": f"Could not reach the model: {e}"}