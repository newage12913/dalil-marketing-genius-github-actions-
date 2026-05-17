import os
import json
import uuid
import random
import subprocess
import requests

from pathlib import Path

# ═════════════════════════════════════════════════════
# DalilENT Media Engine — render_reels.py
# Enterprise Cinematic Medical Reel Renderer
# ═════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"

OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# ═════════════════════════════════════════════════════
# ENV
# ═════════════════════════════════════════════════════

WP_SITE_URL = os.getenv("WP_SITE_URL")
WP_DME_TOKEN = os.getenv("WP_DME_TOKEN")

if not WP_SITE_URL:
    raise RuntimeError("Missing WP_SITE_URL")

if not WP_DME_TOKEN:
    raise RuntimeError("Missing WP_DME_TOKEN")

HEADERS = {
    "X-DME-TOKEN": WP_DME_TOKEN,
    "Content-Type": "application/json"
}

# ═════════════════════════════════════════════════════
# API ENDPOINTS
# ═════════════════════════════════════════════════════

PENDING_JOBS_URL = f"{WP_SITE_URL}/wp-json/dme/v1/pending-jobs"
UPLOAD_VIDEO_URL = f"{WP_SITE_URL}/wp-json/dme/v1/upload-video"

# ═════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════

def log(message):
    print(message)

def run_ffmpeg(command):

    print("\n🎞️ Running FFmpeg...\n")
    print(command)

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:

        print(f"\n❌ FFmpeg failed (exit {result.returncode})")
        print("\nSTDERR:\n")
        print(result.stderr)

        raise RuntimeError("FFmpeg rendering failed")

    return True

def generate_output_name(title):

    safe = title.lower().replace(" ", "_")
    uid = uuid.uuid4().hex[:6]

    return f"{safe}_{uid}.mp4"

def escape_ffmpeg_text(text):

    if not text:
        return ""

    return (
        text.replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace(",", "\\,")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace("%", "\\%")
            .replace('"', '\\"')
            .replace("\n", " ")
    )

# ═════════════════════════════════════════════════════
# FETCH JOBS
# ═════════════════════════════════════════════════════

def fetch_pending_jobs():

    print("\n🌐 Fetching pending jobs...")
    print(f"🔗 URL: {PENDING_JOBS_URL}")

    response = requests.get(
        PENDING_JOBS_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    jobs = response.json()

    print(f"📋 Found {len(jobs)} pending job(s).")

    return jobs

# ═════════════════════════════════════════════════════
# CREATE SUBTITLE FILE
# ═════════════════════════════════════════════════════

def create_srt(job):

    hook = job.get("hook", "")
    reveal = job.get("reveal", "")
    cta = job.get("cta", "")

    srt_path = TEMP_DIR / f"{uuid.uuid4().hex}.srt"

    srt_content = f"""1
00:00:00,000 --> 00:00:05,000
{hook}

2
00:00:06,000 --> 00:00:12,000
{reveal}

3
00:00:13,000 --> 00:00:18,000
{cta}
"""

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    return srt_path

# ═════════════════════════════════════════════════════
# RENDER
# ═════════════════════════════════════════════════════

def render_reel(job):

    title = job.get("title", "untitled")
    image_path = job.get("image")
    music_path = job.get("music")
    duration = int(job.get("duration", 20))

    if not image_path:
        raise RuntimeError("Missing image path")

    if not music_path:
        raise RuntimeError("Missing music path")

    safe_title = escape_ffmpeg_text(title)

    output_name = generate_output_name(title)
    output_path = OUTPUT_DIR / output_name

    subtitle_file = create_srt(job)

    zoom_speed = random.choice([
        "0.001",
        "0.0015",
        "0.002"
    ])

    ffmpeg_cmd = f"""
ffmpeg -y \
-loop 1 -i "{image_path}" \
-i "{music_path}" \
-filter_complex "
[0:v]
scale=1200:2133,
zoompan=
z='min(zoom+{zoom_speed},1.3)':
d={FPS * duration}:
x='iw/2-(iw/zoom/2)':
y='ih/2-(ih/zoom/2)',
scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},
format=yuv420p,
setsar=1,
fade=t=in:st=0:d=1,
fade=t=out:st={duration-1}:d=1
[v1];

[v1]subtitles='{subtitle_file}'[v2];

[v2]drawtext=
fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:
text='DalilENT':
fontcolor=white:
fontsize=32:
box=1:
boxcolor=0xe11d48@0.7:
boxborderw=10:
x=w-text_w-40:
y=h-text_h-40
[vout]
" \
-map "[vout]" \
-map 1:a \
-t {duration} \
-r {FPS} \
-shortest \
-c:v libx264 \
-preset medium \
-crf 18 \
-c:a aac \
-b:a 192k \
-movflags +faststart \
"{output_path}"
"""

    run_ffmpeg(ffmpeg_cmd)

    print(f"\n✅ Render completed: {output_path}")

    return output_path

# ═════════════════════════════════════════════════════
# UPLOAD VIDEO
# ═════════════════════════════════════════════════════

def upload_video(job, video_path):

    print(f"\n📤 Uploading video: {video_path}")

    with open(video_path, "rb") as video_file:

        files = {
            "video": video_file
        }

        data = {
            "job_id": job.get("id")
        }

        response = requests.post(
            UPLOAD_VIDEO_URL,
            headers={
                "X-DME-TOKEN": WP_DME_TOKEN
            },
            files=files,
            data=data,
            timeout=120
        )

    response.raise_for_status()

    print("✅ Upload completed")

# ═════════════════════════════════════════════════════
# PROCESS QUEUE
# ═════════════════════════════════════════════════════

def process_queue():

    try:
        jobs = fetch_pending_jobs()

    except Exception as e:

        print(f"\n❌ Failed to fetch jobs: {e}")
        return

    if not jobs:

        print("\n✅ No jobs to process.")
        return

    success = 0
    failed = 0

    for job in jobs:

        try:

            print("\n──────────────────────────────────────────────────")
            print(f"🔄 Processing Job #{job.get('id')}: {job.get('title')}")

            video_path = render_reel(job)

            upload_video(job, video_path)

            success += 1

            print(f"\n✅ Finished: {job.get('title')}")

        except Exception as e:

            failed += 1

            print(f"\n❌ Failed job: {job.get('title')}")
            print(str(e))

    print("\n============================================================")
    print("🏁 Rendering Complete!")
    print(f"   ✅ Success: {success}")
    print(f"   ❌ Failed:  {failed}")
    print("============================================================")

# ═════════════════════════════════════════════════════
# ENTRY
# ═════════════════════════════════════════════════════

if __name__ == "__main__":

    print("============================================================")
    print("🎬 DalilENT Media Engine — GitHub Actions Renderer")
    print(f"🌐 Target: {WP_SITE_URL}")
    print("============================================================")

    process_queue()
