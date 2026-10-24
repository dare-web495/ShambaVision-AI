import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)
r = requests.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    headers={"x-goog-api-key": os.getenv("GOOGLE_API_KEY")},
)
print(r.status_code, r.text[:300])