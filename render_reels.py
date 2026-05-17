import os
import json
import uuid
import random
import subprocess
from pathlib import Path
from datetime import datetime

# ═════════════════════════════════════════════════════
# DalilENT Media Engine — render_reels.py
# Enterprise Cinematic Medical Reel Renderer
# ═════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
ASSETS_DIR = BASE_DIR / "assets"
FONT_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"

OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# ═════════════════════════════════════════════════════
# STYLE CONFIGS
# ═════════════════════════════════════════════════════

STYLES = {
    "dark_emergency": {
        "font_color": "white",
        "accent": "red",
        "bg": "black"
    },
    "premium_academic": {
        "font_color": "#F5E6C8",
        "accent": "#D4AF37",
        "bg": "#111111"
    },
    "viral_quiz": {
        "font_color": "yellow",
        "accent": "orange",
        "bg": "black"
    }
}

# ═════════════════════════════════════════════════════
# SAMPLE JOB
# ═════════════════════════════════════════════════════

sample_job = {
    "title": "Cholesteatoma",
    "hook": "Would you miss this ENT emergency?",
    "reveal": "This finding may destroy the ossicles.",
    "cta": "Follow DalilENT for daily ENT pearls",
    "image": "assets/images/cholesteatoma.jpg",
    "music": "assets/music/dark_ambient.mp3",
    "style": "dark_emergency",
    "duration": 20
}

# ═════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════


def run_ffmpeg(command):
    print("\n🎬 Running FFmpeg command...")
    result = subprocess.run(command, shell=True)

    if result.returncode != 0:
        raise RuntimeError("FFmpeg rendering failed")



def generate_output_name(title):
    safe = title.lower().replace(" ", "_")
    uid = uuid.uuid4().hex[:6]
    return f"{safe}_{uid}.mp4"



def create_subtitle_file(lines):
    subtitle_path = TEMP_DIR / f"subtitles_{uuid.uuid4().hex[:6]}.srt"

    with open(subtitle_path, "w", encoding="utf-8") as f:
        for idx, item in enumerate(lines, start=1):
            f.write(f"{idx}\n")
            f.write(f"{item['start']} --> {item['end']}\n")
            f.write(f"{item['text']}\n\n")

    return subtitle_path


# ═════════════════════════════════════════════════════
# AI TEXT TIMELINE
# ═════════════════════════════════════════════════════


def build_subtitles(job):
    return [
        {
            "start": "00:00:00,000",
            "end": "00:00:04,000",
            "text": job["hook"]
        },
        {
            "start": "00:00:05,000",
            "end": "00:00:10,000",
            "text": job["reveal"]
        },
        {
            "start": "00:00:12,000",
            "end": "00:00:18,000",
            "text": job["cta"]
        }
    ]


# ═════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ═════════════════════════════════════════════════════


def render_reel(job):
    print("\n🚀 Starting cinematic reel render...")

    style = STYLES.get(job["style"], STYLES["dark_emergency"])

    output_name = generate_output_name(job["title"])
    output_path = OUTPUT_DIR / output_name

    subtitles = build_subtitles(job)
    subtitle_file = create_subtitle_file(subtitles)

    image_path = job["image"]
    music_path = job["music"]

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
 d={FPS * job['duration']}:
 x='iw/2-(iw/zoom/2)':
 y='ih/2-(ih/zoom/2)',
scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},
format=yuv420p,
setsar=1,
fade=t=in:st=0:d=1,
fade=t=out:st={job['duration'] - 1}:d=1
[v];
[v]subtitles='{subtitle_file}'
"
-map "[v]" \
-map 1:a \
-t {job['duration']} \
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

    print(f"\n✅ Render completed: {output_path}")

    return output_path


# ═════════════════════════════════════════════════════
# VIRAL SCORE MOCK
# ═════════════════════════════════════════════════════


def calculate_viral_score(job):
    score = random.randint(70, 98)

    if "emergency" in job["hook"].lower():
        score += 2

    return min(score, 100)


# ═════════════════════════════════════════════════════
# QUEUE PROCESSOR
# ═════════════════════════════════════════════════════


def process_queue(jobs):
    results = []

    for job in jobs:
        try:
            score = calculate_viral_score(job)
            output = render_reel(job)

            results.append({
                "title": job["title"],
                "output": str(output),
                "viral_score": score,
                "status": "success"
            })

        except Exception as e:
            results.append({
                "title": job["title"],
                "status": "failed",
                "error": str(e)
            })

    return results


# ═════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🧠 DalilENT Media Engine")
    print("🎥 Cinematic Medical Reel Renderer")
    print("══════════════════════════════════")

    queue = [sample_job]

    results = process_queue(queue)

    print("\n📊 FINAL RESULTS")
    print(json.dumps(results, indent=2))
