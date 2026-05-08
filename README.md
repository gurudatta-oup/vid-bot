# 🎬 Video Pipeline

Automated YouTube Shorts generator for coding language facts.
Triggered manually via GitHub Actions — no cron, fully on-demand.

## How It Works

```
Manual Trigger
     ↓
VM 1 — Generate script (Gemini API)
     ↓
VM 2 — Generate voiceover (gTTS)
     ↓
VM 3 — Assemble video (Pexels + FFmpeg)
     ↓
VM 4 — Save artifacts (video.mp4 + done.json)
```

Each stage runs on its own GitHub Actions runner (separate VM).
Files pass between stages via GitHub Artifacts.

## Setup

### 1. Add Secrets
Go to `Settings → Secrets → Actions` and add:

| Secret | Where to get it |
|---|---|
| `GEMINI_KEY` | https://aistudio.google.com/app/apikey |
| `PEXELS_KEY` | https://www.pexels.com/api/ |

### 2. Run the Pipeline
Go to `Actions → 🎬 Video Pipeline → Run workflow`

Optionally enter a topic override, or leave blank for AI to choose.

### 3. Download Your Video
After the run completes, go to the run summary and download:
- `video-bundle-{run_number}` → contains `reel.mp4` + `done.json`
- `done-json` → persistent history used by the next run

## done.json
Tracks all videos made so topics never repeat.
Automatically downloaded at the start of each run and updated at the end.

Stores last 60 topics and last 15 languages to ensure rotation.

## File Structure

```
.github/workflows/pipeline.yml   ← GitHub Actions workflow
scripts/
  generate.py                    ← Gemini API script generation
  audio.py                       ← gTTS voiceover
  video.py                       ← Pexels + FFmpeg assembly
requirements/
  generate.txt
  audio.txt
  video.txt
prompt.txt                       ← Master AI prompt
config.json                      ← Video settings
done.json                        ← History tracker (also in artifacts)
```
