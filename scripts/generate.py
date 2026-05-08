import json
import datetime
import requests
import os
import sys

GEMINI_KEY    = os.environ["GEMINI_KEY"]
TOPIC_OVERRIDE = os.environ.get("TOPIC_OVERRIDE", "")
DONE_FILE     = "done.json"
PROMPT_FILE   = "prompt.txt"
OUTPUT_FILE   = "output/script.json"

# ── Load history ──────────────────────────────────────────────────────────────
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

# ── Save updated history ───────────────────────────────────────────────────────
def save_done(done, new_entry):
    done["videos"].append(new_entry)
    done["used_topics"].append(new_entry["topic"])
    done["used_languages"].append(new_entry["language"])

    # rolling window — keep last 60 topics, last 15 languages
    done["used_topics"]    = done["used_topics"][-60:]
    done["used_languages"] = done["used_languages"][-15:]
    done["last_updated"]   = str(datetime.date.today())

    with open(DONE_FILE, "w") as f:
        json.dump(done, f, indent=2)

    print(f"📝 done.json updated — {len(done['videos'])} total videos")

# ── Build prompt ───────────────────────────────────────────────────────────────
def build_prompt(done):
    with open(PROMPT_FILE, "r") as f:
        prompt = f.read()

    used_topics = "\n".join(f"- {t}" for t in done["used_topics"]) or "None yet — this is the first video!"
    used_langs  = ", ".join(done["used_languages"][-10:]) or "None yet"

    return (prompt
        .replace("{DATE}",           str(datetime.date.today()))
        .replace("{USED_TOPICS}",    used_topics)
        .replace("{USED_LANGUAGES}", used_langs)
        .replace("{TOPIC_OVERRIDE}", TOPIC_OVERRIDE))

# ── Call Gemini API ────────────────────────────────────────────────────────────
def call_gemini(prompt):
    url = (
        "https://generativelanguage.googleapis.com/v1beta"
        f"/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 1500
        }
    }

    print("🤖 Calling Gemini API...")
    res = requests.post(url, json=payload, timeout=60)

    if res.status_code != 200:
        print(f"❌ Gemini error {res.status_code}: {res.text}")
        sys.exit(1)

    raw = res.json()["candidates"][0]["content"]["parts"][0]["text"]

    # strip markdown fences if model adds them
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    return json.loads(raw.strip())

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)

    done   = load_done()
    prompt = build_prompt(done)
    script = call_gemini(prompt)

    # validate required fields
    required = ["date", "language", "topic", "title", "script",
                "search_keywords", "tags", "description", "thumbnail_text"]
    missing = [k for k in required if k not in script]
    if missing:
        print(f"❌ Missing fields in response: {missing}")
        sys.exit(1)

    # save script for downstream jobs
    with open(OUTPUT_FILE, "w") as f:
        json.dump(script, f, indent=2)

    print(f"✅ Script saved: {script['title']}")
    print(f"💻 Language   : {script['language']}")
    print(f"📌 Topic      : {script['topic']}")

    # write to done.json (status = pending until finalize job)
    save_done(done, {
        "date":         script["date"],
        "language":     script["language"],
        "topic":        script["topic"],
        "title":        script["title"],
        "tags":         script["tags"],
        "status":       "pending",
        "youtube_id":   "",
        "run_number":   os.environ.get("GITHUB_RUN_NUMBER", "")
    })
