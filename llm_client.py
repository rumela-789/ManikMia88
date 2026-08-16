# src/llm_client.py
"""
Gemini API (ফ্রি টায়ার) দিয়ে টেক্সট জেনারেট করার সাধারণ wrapper।
API key .env / GitHub Secrets থেকে GEMINI_API_KEY নামে আসবে।
"""

import os
import time
import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest") # ফ্রি টায়ারে সবচেয়ে stable choice
BASE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def call_gemini(system_prompt: str, user_content: str, max_retries: int = 3) -> str:
    """
    Gemini API কল করে টেক্সট রেসপন্স ফেরত দেয়।
    429 (rate limit) এলে exponential backoff দিয়ে রিট্রাই করে।
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable সেট করা নেই।")

    url = f"{BASE_URL}?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        },
    }

    delay = 2
    for attempt in range(max_retries):
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                return "[error] খালি রেসপন্স পাওয়া গেছে।"
        elif resp.status_code == 429:
            print(f"[warn] Rate limited (429). {delay}s পর রিট্রাই করছি...")
            time.sleep(delay)
            delay *= 2
        else:
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")

    raise RuntimeError("বারবার rate-limit হওয়ায় রিকোয়েস্ট ব্যর্থ হয়েছে।")
