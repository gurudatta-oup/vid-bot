import json
import os
import re
import sys
import math
import subprocess
import requests
import urllib.request

# ── Config ─────────────────────────────────────────────────────────────────────
SCRIPT_FILE  = "output/script.json"
AUDIO_FILE   = "output/voiceover.mp3"
OUTPUT_FILE  = "output/reel.mp4"
CLIPS_DIR    = "output/clips"
CONFIG_FILE  = "config.json"

PEXELS_KEY   = os.environ.get("PEXELS_KEY", "")
W, H         = 1080, 1920

# ── Load files ─────────────────────────────────────────────────────────────────
def load_files():
    with open(SCRIPT_FILE, "r") as f:
        script = json.load(f)
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    return script, config

# ── Get audio duration via ffprobe ─────────────────────────────────────────────
def get_audio_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())

# ── Fetch stock clips from Pexels ──────────────────────────────────────────────
def fetch_pexels_clips(keywords, total_duration):
    os.makedirs(CLIPS_DIR, exist_ok=True)
    downloaded = []

    if not PEXELS_KEY:
        print("⚠️  No PEXELS_KEY — using colour background fallback")
        return []

    headers = {"Authorization": PEXELS_KEY}

    for idx, keyword in enumerate(keywords[:3]):
        print(f"🔍 Searching Pexels: '{keyword}'")
        url = "https://api.pexels.com/videos/search"
        params = {"query": keyword, "orientation": "portrait",
                  "size": "medium", "per_page": 3}
        res = requests.get(url, headers=headers, params=params, timeout=15)

        if res.status_code != 200:
            print(f"  ⚠️  Pexels error {res.status_code} for '{keyword}'")
            continue

        videos = res.json().get("videos", [])
        if not videos:
            print(f"  ⚠️  No results for '{keyword}'")
            continue

        video     = videos[0]
        # prefer HD portrait file
        files     = sorted(video["video_files"],
                           key=lambda f: f.get("width", 0), reverse=False)
        portrait  = [f for f in files if f.get("width", 999) <= 1080]
        chosen    = portrait[0] if portrait else files[0]

        clip_path = os.path.join(CLIPS_DIR, f"clip_{idx}.mp4")
        print(f"  ⬇️  Downloading clip {idx+1}...")
        urllib.request.urlretrieve(chosen["link"], clip_path)
        downloaded.append(clip_path)
        print(f"  ✅ Saved: {clip_path}")

    return downloaded

# ── Build caption chunks (N words per line) ────────────────────────────────────
def build_captions(clean_script, total_duration, words_per_chunk=4):
    words  = clean_script.split()
    chunks = [words[i:i+words_per_chunk]
              for i in range(0, len(words), words_per_chunk)]
    t_each = total_duration / len(chunks) if chunks else 1
    captions = []
    for i, chunk in enumerate(chunks):
        captions.append({
            "text":  " ".join(chunk).upper(),
            "start": round(i * t_each, 3),
            "end":   round((i + 1) * t_each, 3)
        })
    return captions

# ── Generate subtitle file (ASS format for styled captions) ───────────────────
def write_ass(captions, path):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,Italic,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV
Style: Default,Arial,72,&H00FFFFFF,&H00000000,&H80000000,-1,0,1,4,2,2,60,60,400

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    def fmt_time(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    lines = [header]
    for cap in captions:
        lines.append(
            f"Dialogue: 0,{fmt_time(cap['start'])},{fmt_time(cap['end'])},"
            f"Default,,0,0,0,,{cap['text']}"
        )
    with open(path, "w") as f:
        f.write("\n".join(lines))

# ── Build final video with FFmpeg ──────────────────────────────────────────────
def assemble(clips, audio_duration, captions_ass):
    os.makedirs("output", exist_ok=True)

    if clips:
        # ── build looped clip input ──────────────────────────────────────────
        concat_file = "output/concat.txt"
        # repeat clips enough to cover full audio duration
        total_clip_dur = 0
        repeated = []
        clip_durations = []

        for c in clips:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", c],
                capture_output=True, text=True)
            try:
                d = float(r.stdout.strip())
            except ValueError:
                d = 10.0
            clip_durations.append(d)

        idx = 0
        while total_clip_dur < audio_duration + 2:
            repeated.append(clips[idx % len(clips)])
            total_clip_dur += clip_durations[idx % len(clips)]
            idx += 1

        with open(concat_file, "w") as f:
            for c in repeated:
                f.write(f"file '{os.path.abspath(c)}'\n")

        # scale + crop to 1080x1920
        bg_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                   f"crop={W}:{H},setsar=1",
            "-t", str(audio_duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an", "output/bg.mp4"
        ]
    else:
        # fallback: dark gradient background
        bg_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x1a1a2e:size={W}x{H}:rate=30",
            "-t", str(audio_duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "output/bg.mp4"
        ]

    print("🎞️  Building background...")
    subprocess.run(bg_cmd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ── burn captions + mix audio ────────────────────────────────────────────
    print("🔤 Burning captions + mixing audio...")
    final_cmd = [
        "ffmpeg", "-y",
        "-i", "output/bg.mp4",
        "-i", AUDIO_FILE,
        "-vf", f"ass={captions_ass}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        OUTPUT_FILE
    ]
    subprocess.run(final_cmd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)

    for f in [SCRIPT_FILE, AUDIO_FILE]:
        if not os.path.exists(f):
            print(f"❌ Missing: {f}")
            sys.exit(1)

    script, config = load_files()
    keywords       = script.get("search_keywords", ["coding", "programming", "technology"])
    clean_script   = script.get("clean_script", script.get("script", ""))
    clean_script   = re.sub(r"\[.*?\]", "", clean_script).strip()

    print(f"🎬 Assembling: {script['title']}")

    audio_dur = get_audio_duration(AUDIO_FILE)
    print(f"⏱️  Audio duration: {audio_dur:.1f}s")

    clips       = fetch_pexels_clips(keywords, audio_dur)
    captions    = build_captions(clean_script, audio_dur,
                                  config["captions"]["words_per_caption"])
    ass_path    = "output/captions.ass"
    write_ass(captions, ass_path)

    assemble(clips, audio_dur, ass_path)

    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"✅ Video ready: {OUTPUT_FILE} ({size_mb:.1f} MB)")
    print(f"🎉 Done! '{script['title']}'")
