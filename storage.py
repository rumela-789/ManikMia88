# src/storage.py
"""
জেনারেট করা আর্টিকেলগুলো সংরক্ষণ করে।
সবচেয়ে সহজ ফ্রি পদ্ধতি: data/ ফোল্ডারে JSON ফাইল হিসেবে সেভ করা এবং
GitHub Actions সেটা repo-তে commit করে দেয় (কোনো আলাদা ডাটাবেস লাগে না)।

চাইলে পরে Supabase/PostgreSQL-এ সহজেই মাইগ্রেট করা যাবে —
এই ফাইলের save_daily_run() ফাংশনটা শুধু বদলালেই হবে।
"""

import json
import os
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RETENTION_DAYS = 30  # এর চেয়ে পুরনো দিনের আর্টিকেল অটো-ডিলিট হবে


def save_daily_run(results: dict) -> str:
    """
    results = {
        "date": "2026-08-16",
        "agents": { "world_politics": "...", ... },
        "final_column": "..."
    }
    ফাইল সেভ হয় data/YYYY-MM-DD.json হিসেবে, আর data/latest.json-ও আপডেট হয়
    (ফ্রন্টএন্ড সহজে সবসময় সর্বশেষটা দেখাতে পারবে)।
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    date_str = results.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    path = os.path.join(DATA_DIR, f"{date_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    latest_path = os.path.join(DATA_DIR, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # index.json — ফ্রন্টএন্ডে "আর্কাইভ" লিস্ট দেখানোর জন্য
    index_path = os.path.join(DATA_DIR, "index.json")
    index = []
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    if date_str not in index:
        index.append(date_str)
        index.sort(reverse=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    cleanup_old_articles(index_path)

    return path


def cleanup_old_articles(index_path: str) -> None:
    """
    RETENTION_DAYS (ডিফল্ট ৩০ দিন)-এর চেয়ে পুরনো তারিখের data/YYYY-MM-DD.json
    ফাইলগুলো ডিলিট করে এবং index.json থেকেও বাদ দেয়।
    (latest.json কখনো ডিলিট হয় না — সেটা সবসময় সর্বশেষ কলাম ধরে রাখে।)
    """
    if not os.path.exists(index_path):
        return

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=RETENTION_DAYS)
    kept = []
    for date_str in index:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            kept.append(date_str)  # অচেনা ফরম্যাট হলে না ছুঁয়েই রাখি
            continue

        if d < cutoff:
            file_path = os.path.join(DATA_DIR, f"{date_str}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[cleanup] {RETENTION_DAYS} দিনের পুরনো আর্টিকেল ডিলিট হলো: {date_str}")
        else:
            kept.append(date_str)

    if kept != index:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(kept, f, ensure_ascii=False, indent=2)
