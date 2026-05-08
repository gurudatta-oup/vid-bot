import json
import datetime
import requests
import os
import sys

TOPIC_OVERRIDE = os.environ.get("TOPIC_OVERRIDE", "")
DONE_FILE      = "done.json"
PROMPT_FILE    = "prompt.txt"
OUTPUT_FILE    = "output/script.json"
OLLAMA_URL     = "http://localhost:11434/api/generate"
MODEL          = "phi3:mini"

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

def call_ollama(prompt):
    print(f"🤖 Calling Ollama ({MODEL})...")
    payload = {
        "model":  MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.9,
            "num_predict": 1500
        }
    }
    res = requests.post(OLLAMA_URL, json=payload, timeout=300)

    if res.status_code != 200:
        print(f"❌ Ollama error {res.status_code}: {res.text}")
        sys.exit(1)

    raw = res.json()["response"]
    print("✅ Ollama responded")
    return parse_response(raw)

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)

    done   = load_done()
    prompt = build_prompt(done)
    script = call_ollama(prompt)

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