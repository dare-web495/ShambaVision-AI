import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)
model = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
r = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    headers={"x-goog-api-key": os.getenv("GOOGLE_API_KEY")},
    json={"contents": [{"parts": [{"text": "Say hello in Swahili."}]}]},
)
print(model, r.status_code, r.text[:400])