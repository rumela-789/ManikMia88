# src/fetch_news.py
"""
গত ২৪ ঘণ্টার বিশ্ব সংবাদ ডেটা সংগ্রহ করে — সম্পূর্ণ ফ্রি সোর্স ব্যবহার করে:
1. GDELT Project (news + events, no API key লাগে না, রেট লিমিট নেই মূলত)
2. Reuters World / AP / BBC-এর পাবলিক RSS ফিড (headline-level, লিংকসহ)

এই ফাংশনগুলো raw উপাত্ত সংগ্রহ করে, যা পরে প্রতিটা এজেন্টের প্রম্পটে ইনপুট হিসেবে যাবে।
"""

import requests
import feedparser
from datetime import datetime, timedelta, timezone

# পাবলিক, ফ্রি RSS ফিড (কোনো API key দরকার নেই)
RSS_FEEDS = {
    "reuters_world": "https://www.reutersagency.com/feed/?best-topics=world&post_type=best",
    "bbc_world": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "ap_topnews": "https://apnews.com/apf-topnews?output=rss",  # fallback হতে পারে, না চললে বাদ দাও
    "aljazeera": "https://www.aljazeera.com/xml/rss/all.xml",
}

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def fetch_rss_headlines(max_per_feed: int = 15) -> list[dict]:
    """সব RSS ফিড থেকে গত ২৪ ঘণ্টার হেডলাইন সংগ্রহ করে।"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    items = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                items.append({
                    "source": source,
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:400],
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"[warn] RSS fetch failed for {source}: {e}")
    return items


def fetch_gdelt(query: str, max_records: int = 30) -> list[dict]:
    """
    GDELT থেকে নির্দিষ্ট বিষয়ে গত ২৪ ঘণ্টার সংবাদ খোঁজে।
    query উদাহরণ: "politics", "economy inflation", "military conflict"
    """
    params = {
        "query": f"{query} sourcelang:eng",
        "mode": "artlist",
        "maxrecords": max_records,
        "timespan": "24h",
        "format": "json",
    }
    try:
        resp = requests.get(GDELT_DOC_API, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        articles = data.get("articles", [])
        return [
            {
                "title": a.get("title"),
                "url": a.get("url"),
                "domain": a.get("domain"),
                "seendate": a.get("seendate"),
            }
            for a in articles
        ]
    except Exception as e:
        print(f"[warn] GDELT fetch failed for query='{query}': {e}")
        return []


def collect_daily_dataset() -> dict:
    """
    সব এজেন্টের জন্য একবারে raw ডেটা সংগ্রহ করে একটা dict-এ রাখে।
    এটা main.py থেকে দিনে একবার কল হবে, তারপর প্রতিটা এজেন্ট এখান থেকে
    প্রাসঙ্গিক অংশ নিয়ে কাজ করবে (API কল বাঁচাতে raw fetch একবারই হয়)।
    """
    dataset = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "rss_headlines": fetch_rss_headlines(),
        "gdelt_politics": fetch_gdelt("politics government election"),
        "gdelt_economy": fetch_gdelt("economy inflation market central bank"),
        "gdelt_conflict": fetch_gdelt("military conflict war"),
        "gdelt_diplomacy": fetch_gdelt("diplomacy summit sanctions treaty"),
        "gdelt_technology": fetch_gdelt("artificial intelligence technology policy"),
    }
    return dataset


if __name__ == "__main__":
    import json
    ds = collect_daily_dataset()
    print(json.dumps(ds, indent=2, ensure_ascii=False)[:2000])
