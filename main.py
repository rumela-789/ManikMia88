# src/main.py
"""
প্রধান orchestrator — এটাই GitHub Actions প্রতিদিন একবার রান করবে।

ধাপ:
1. গত ২৪ ঘণ্টার raw নিউজ ডেটা সংগ্রহ (একবারই — সব এজেন্ট শেয়ার করে, API/রেট বাঁচাতে)
2. ৯টা বিশেষজ্ঞ এজেন্ট প্রত্যেকে নিজ নিজ বিষয়ে বিশ্লেষণ লেখে
3. Chief Analyst Agent সব একত্র করে একটা ফাইনাল কলাম লেখে
4. ফলাফল data/ ফোল্ডারে সেভ হয়
"""

import time
from datetime import datetime, timezone

from fetch_news import collect_daily_dataset
from llm_client import call_gemini
from storage import save_daily_run
from personas import AGENTS, get_agent


def build_user_prompt_for_research_agent(agent: dict, dataset: dict) -> str:
    """প্রতিটা রিসার্চ এজেন্টের জন্য প্রাসঙ্গিক raw ডেটা + নির্দেশনা প্যাক করে।"""
    return f"""
নিচে গত ২৪ ঘণ্টার সংগৃহীত raw সংবাদ উপাত্ত দেওয়া হলো (RSS হেডলাইন + GDELT আর্টিকেল তালিকা)।
তোমার ফোকাস ক্ষেত্র: {agent['focus']}

=== RSS হেডলাইন ===
{format_items(dataset.get('rss_headlines', [])[:25])}

=== GDELT: রাজনীতি ===
{format_items(dataset.get('gdelt_politics', [])[:15])}

=== GDELT: অর্থনীতি ===
{format_items(dataset.get('gdelt_economy', [])[:15])}

=== GDELT: সংঘাত/নিরাপত্তা ===
{format_items(dataset.get('gdelt_conflict', [])[:15])}

=== GDELT: কূটনীতি ===
{format_items(dataset.get('gdelt_diplomacy', [])[:15])}

=== GDELT: প্রযুক্তি ===
{format_items(dataset.get('gdelt_technology', [])[:15])}

উপরের উপাত্ত থেকে শুধু তোমার ফোকাস ক্ষেত্রের সাথে প্রাসঙ্গিক অংশ বেছে নিয়ে
তোমার বিশ্লেষণ লেখো (৩০০-৫০০ শব্দ, বাংলায়)। প্রতিটা গুরুত্বপূর্ণ দাবির সাথে উৎস উল্লেখ করো।
"""


def format_items(items: list[dict]) -> str:
    lines = []
    for it in items:
        title = it.get("title", "")
        source = it.get("source") or it.get("domain") or ""
        link = it.get("link") or it.get("url") or ""
        if title:
            lines.append(f"- {title} [{source}] ({link})")
    return "\n".join(lines) if lines else "(কোনো ডেটা পাওয়া যায়নি)"


def run():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"[{today}] দৈনিক এজেন্ট রান শুরু হচ্ছে...")

    dataset = collect_daily_dataset()

    research_agents = [a for a in AGENTS if a["id"] != "chief_analyst"]
    agent_outputs = {}

    for agent in research_agents:
        print(f"  -> {agent['name']} চালু হচ্ছে...")
        prompt = build_user_prompt_for_research_agent(agent, dataset)
        try:
            output = call_gemini(agent["system_prompt"], prompt)
        except Exception as e:
            output = f"[error] {agent['name']} ব্যর্থ হয়েছে: {e}"
            print(f"     [error] {e}")
        agent_outputs[agent["id"]] = {
            "name": agent["name"],
            "content": output,
        }
        time.sleep(4)  # ফ্রি টায়ারের RPM লিমিট মেনে চলার জন্য সামান্য বিরতি

    # --- Chief Analyst: সব একত্র করে ফাইনাল কলাম ---
    chief = get_agent("chief_analyst")
    combined_reports = "\n\n".join(
        f"### {v['name']}\n{v['content']}" for v in agent_outputs.values()
    )
    print("  -> Chief Analyst ফাইনাল কলাম লিখছে...")
    try:
        final_column = call_gemini(chief["system_prompt"], combined_reports)
    except Exception as e:
        final_column = f"[error] Chief Analyst ব্যর্থ হয়েছে: {e}"

    results = {
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agents": agent_outputs,
        "final_column": final_column,
    }

    path = save_daily_run(results)
    print(f"সম্পন্ন। সেভ হয়েছে: {path}")


if __name__ == "__main__":
    run()
