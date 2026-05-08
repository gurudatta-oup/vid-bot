import json
import datetime
import requests
import os
import sys
import time

GEMINI_KEY     = os.environ["GEMINI_KEY"]
TOPIC_OVERRIDE = os.environ.get("TOPIC_OVERRIDE", "")
DONE_FILE      = "done.json"
PROMPT_FILE    = "prompt.txt"
OUTPUT_FILE    = "output/script.json"

# Try models in order — most free-tier friendly first
MODELS = [
    "gemini-2.0-flash-lite",  # highest free limits
    "gemini-1.5-flash-8b",    # very generous free tier
    "gemini-1.5-flash",       # solid fallback
    "gemini-2.0-flash",       # lower free quota
]

def load_done():
    try:
        with open(DONE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "videos": [],
            "used_languages": [],
            "used_topics": [],
            "last_updated": ""
        }

def save_done(done, new_entry):
    done["videos"].append(new_entry)
    done["used_topics"].append(new_entry["topic"])
    done["used_languages"].append(new_entry["language"])
    done["used_topics"]    = done["used_topics"][-60:]
    done["used_languages"] = done["used_languages"][-15:]
    done["last_updated"]   = str(datetime.date.today())
    with open(DONE_FILE, "w") as f:
        json.dump(done, f, indent=2)
    print(f"📝 done.json updated — {len(done['videos'])} total videos")

def build_prompt(done):
    with open(PROMPT_FILE, "r") as f:
        prompt = f.read()
    used_topics = "\n".join(f"- {t}" for t in done["used_topics"]) or "None yet"
    used_langs  = ", ".join(done["used_languages"][-10:]) or "None yet"
    return (prompt
        .replace("{DATE}",           str(datetime.date.today()))
        .replace("{USED_TOPICS}",    used_topics)
        .replace("{USED_LANGUAGES}", used_langs)
        .replace("{TOPIC_OVERRIDE}", TOPIC_OVERRIDE))

def parse_response(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return json.loads(raw.strip())

def call_gemini(prompt):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 1500}
    }

    for model in MODELS:
        url = (
            "https://generativelanguage.googleapis.com/v1beta"
            f"/models/{model}:generateContent?key={GEMINI_KEY}"
        )
        print(f"🤖 Trying: {model}")

        for attempt in range(3):
            res = requests.post(url, json=payload, timeout=60)

            if res.status_code == 200:
                raw = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                print(f"✅ Success with {model}")
                return parse_response(raw)

            elif res.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  ⚠️  429 quota (attempt {attempt+1}/3) — waiting {wait}s...")
                time.sleep(wait)

            else:
                print(f"  ❌ Error {res.status_code} — trying next model")
                break

        print(f"  ⏭️  Next model...")

    print("❌ All models quota exhausted.")
    print("💡 Get a new key: https://aistudio.google.com/app/apikey")
    sys.exit(1)

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)

    done   = load_done()
    prompt = build_prompt(done)
    script = call_gemini(prompt)

    required = ["date", "language", "topic", "title", "script",
                "search_keywords", "tags", "description", "thumbnail_text"]
    missing = [k for k in required if k not in script]
    if missing:
        print(f"❌ Missing fields: {missing}")
        sys.exit(1)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(script, f, indent=2)

    print(f"✅ Script : {script['title']}")
    print(f"💻 Lang   : {script['language']}")
    print(f"📌 Topic  : {script['topic']}")

    save_done(done, {
        "date":       script["date"],
        "language":   script["language"],
        "topic":      script["topic"],
        "title":      script["title"],
        "tags":       script["tags"],
        "status":     "pending",
        "youtube_id": "",
        "run_number": os.environ.get("GITHUB_RUN_NUMBER", "")
    })