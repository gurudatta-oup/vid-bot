import json
import os
import re
import sys

from gtts import gTTS

SCRIPT_FILE = "output/script.json"
AUDIO_FILE  = "output/voiceover.mp3"

# ── Strip stage direction tags from script ─────────────────────────────────────
def clean_script(raw: str) -> str:
    text = re.sub(r"\[VISUAL:[^\]]*\]", "", raw)   # remove [VISUAL: ...]
    text = re.sub(r"\[PAUSE:[^\]]*\]",  " ", text)  # replace [PAUSE: Xs] with space
    text = re.sub(r"\s{2,}",            " ", text)  # collapse extra spaces
    return text.strip()

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)

    if not os.path.exists(SCRIPT_FILE):
        print(f"❌ Script file not found: {SCRIPT_FILE}")
        sys.exit(1)

    with open(SCRIPT_FILE, "r") as f:
        script = json.load(f)

    raw_script = script.get("script", "")
    if not raw_script:
        print("❌ Script field is empty")
        sys.exit(1)

    clean = clean_script(raw_script)
    print(f"🎙️ Generating voiceover ({len(clean.split())} words)...")
    print(f"📝 Preview: {clean[:120]}...")

    tts = gTTS(text=clean, lang="en", tld="com", slow=False)
    tts.save(AUDIO_FILE)

    size_kb = os.path.getsize(AUDIO_FILE) / 1024
    print(f"✅ Voiceover saved: {AUDIO_FILE} ({size_kb:.1f} KB)")

    # also save cleaned script for caption generation
    script["clean_script"] = clean
    with open(SCRIPT_FILE, "w") as f:
        json.dump(script, f, indent=2)
