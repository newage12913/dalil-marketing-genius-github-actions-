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

def run_ffmpeg(command):
    print("\n🎬 Running FFmpeg...")
    result = subprocess.run(command, shell=True)

    if result.returncode != 0:
        raise RuntimeError("FFmpeg failed")

def generate_output_name(title):
    safe = title.lower().replace(" ", "_")
    uid = uuid.uuid4().hex[:6]
    return f"{safe}_{uid}.mp4"

# ═════════════════════════════════════════════════════
# FETCH JOBS
# ═════════════════════════════════════════════════════

def fetch_pending_jobs():

    print("\n🌐 Fetching pending jobs...")
    print(f"URL: {PENDING_JOBS_URL}")

    response = requests.get(
        PENDING_JOBS_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    jobs = response.json()

    print(f"✅ Found {len(jobs)} pending jobs")

    return jobs

# ═════════════════════════════════════════════════════
# RENDER
# ═════════════════════════════════════════════════════

def render_reel(job):

    title = job.get("title", "untitled")
    image_path = job.get("image")
    music_path = job.get("music")
    duration = int(job.get("duration", 20))

    output_name = generate_output_name(title)
    output_path = OUTPUT_DIR / output_name

    zoom_speed = random.choice([
        "0.001",
        "0.0015",
        "0.002"
    ])

    ffmpeg_cmd = f'''
ffmpeg -y \
-loop 1 -i "{image_path}" \
-i "{music_path}" \
-filter_complex "
[0:v]
scale=1200:2133,
zoompan=z='min(zoom+{zoom_speed},1.3)':
d={FPS * duration}:
x='iw/2-(iw/zoom/2)':
y='ih/2-(ih/zoom/2)',
scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},
format=yuv420p,
setsar=1
[v]
" \
-map "[v]" \
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
'''

    run_ffmpeg(ffmpeg_cmd)

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

    for job in jobs:

        try:
            print(f"\n🚀 Processing: {job.get('title')}")

            video_path = render_reel(job)

            upload_video(job, video_path)

            print(f"\n✅ Finished: {job.get('title')}")

        except Exception as e:
            print(f"\n❌ Failed job: {job.get('title')}")
            print(str(e))

# ═════════════════════════════════════════════════════
# ENTRY
# ═════════════════════════════════════════════════════

if __name__ == "__main__":

    print("\n============================================================")
    print("🎬 DalilENT Media Engine — GitHub Actions Renderer")
    print(f"🌐 Target: {WP_SITE_URL}")
    print("============================================================")

    process_queue()
