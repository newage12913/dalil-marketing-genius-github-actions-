#!/usr/bin/env python3
"""
DalilENT Media Engine — GitHub Actions Renderer
Fetches pending jobs from WordPress REST API, renders videos with FFmpeg, uploads back.
"""

import os
import sys
import re
import json
import base64
import requests
import subprocess
import urllib.request
import textwrap
from pathlib import Path
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────────────────
WP_SITE_URL  = os.environ.get('WP_SITE_URL', '').rstrip('/').strip()
WP_DME_TOKEN = os.environ.get('WP_DME_TOKEN', '').strip()

HEADERS = {
    'X-DME-Token': WP_DME_TOKEN,
    'Content-Type': 'application/json',
}

WORK_DIR = Path('render_workspace')
LOG_DIR  = Path('render_logs')
WORK_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# Video specs — Cinematic Vertical 9:16
VIDEO_W   = 1080
VIDEO_H   = 1920
VIDEO_FPS = 30
VIDEO_DUR = 20  # seconds

# Font path on Ubuntu (installed by apt)
FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

# ─── Helpers ─────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)
    with open(LOG_DIR / 'render.log', 'a', encoding='utf-8') as f:
        f.write(f"[{ts}] {msg}\n")


def fetch_pending_jobs():
    url = f"{WP_SITE_URL}/wp-json/dme/v1/pending-jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data.get('jobs', [])
    except Exception as e:
        log(f"❌ Failed to fetch jobs: {e}")
        return []


def download_image(url, dest_path):
    try:
        urllib.request.urlretrieve(url, dest_path)
        return True
    except Exception as e:
        log(f"  ⚠️  Image download failed: {e}")
        return False


def get_original_wp_image_url(url):
    """Strip WordPress image size suffixes (e.g. -150x150, -300x300, -1024x1024) to get the original image URL."""
    if not url:
        return ""
    # Matches patterns like -150x150 or -768x512 before the file extension at the end of the URL
    cleaned_url = re.sub(r'-\d+x\d+(?=\.[a-zA-Z0-9]+$)', '', url)
    return cleaned_url


def wrap_text(text, max_chars=35):
    """Wrap long text and center-align each line using space padding."""
    if not text:
        return ""
    # Standard wrap
    lines = textwrap.wrap(text, width=max_chars)
    if not lines:
        return text
    # Find max line length
    max_len = max(len(l) for l in lines)
    # Center each line using padding so that drawtext looks beautifully centered
    centered_lines = [l.center(max_len) for l in lines]
    return '\n'.join(centered_lines)


def escape_ffmpeg_text(text):
    """Escape special characters for FFmpeg drawtext filter with double quotes."""
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')  # Escape double quotes since we wrap in double quotes
    text = text.replace("'", "'")    # Keep single quotes as literal
    text = text.replace(':', '\\:')
    text = text.replace('[', '\\[').replace(']', '\\]')
    # Limit length
    return text[:120] if len(text) > 120 else text


def render_video(job_id, image_path, script, style, output_path):
    # Wrap text for multiple lines beautifully
    hook_wrapped   = wrap_text(script.get('hook', 'DalilENT Medical Education'), 30)
    reveal_wrapped = wrap_text(script.get('reveal_text', 'Medical Finding'), 24)
    pearl_wrapped  = wrap_text(script.get('pearl_text', 'Key clinical pearl'), 35)

    hook_file   = WORK_DIR / f"hook_{job_id}.txt"
    reveal_file = WORK_DIR / f"reveal_{job_id}.txt"
    pearl_file  = WORK_DIR / f"pearl_{job_id}.txt"

    # Write files in UTF-8
    with open(hook_file, 'w', encoding='utf-8') as f:
        f.write(hook_wrapped)
    with open(reveal_file, 'w', encoding='utf-8') as f:
        f.write(reveal_wrapped)
    with open(pearl_file, 'w', encoding='utf-8') as f:
        f.write(pearl_wrapped)

    # ─── Color Palette by Style ───────────────────────────────────────────────
    if style == 'premium_academic':
        bg_color       = '0x1a1a2e'
        accent_color   = '0xf59e0b'  # Gold
        overlay_alpha  = '0.35'      # Subtle premium overlay for bright background
    elif style == 'viral_quiz':
        bg_color       = '0x0f172a'
        accent_color   = '0x8b5cf6'  # Purple
        overlay_alpha  = '0.40'      # Dynamic overlay
    else:  # dark_emergency
        bg_color       = '0x0f0f1a'
        accent_color   = '0xe11d48'  # Emergency Red
        overlay_alpha  = '0.45'      # Dramatic overlay but still highly visible

    # ─── Build FFmpeg Filter Graph ────────────────────────────────────────────
    # Using textfile avoids any quoting or escaping issues in drawtext.
    # Paths must be passed with forward slashes to FFmpeg even on Windows.
    hook_file_str   = str(hook_file).replace('\\', '/')
    reveal_file_str = str(reveal_file).replace('\\', '/')
    pearl_file_str  = str(pearl_file).replace('\\', '/')

    # To achieve ultra-sharp, cinematic 8K-like quality and bypass the blurry, pixelated
    # default scaling of FFmpeg's zoompan, we use Supersampling:
    # 1. Scale the input image up to 2160x3840 using the premium Lanczos filter.
    # 2. Run the zoompan filter at full 2160x3840 resolution.
    # 3. Downscale the resulting video back to 1080x1920 using Lanczos for extremely crisp details.
    filter_complex = (
        # Step 1: Scale input up to 2160x3840 with high-quality Lanczos scaling
        f"[0:v]scale=2160:3840:flags=lanczos,"
        # Step 2: Apply zoompan at 4K canvas size (2160x3840) to preserve pristine pixel detail
        f"zoompan=z='min(zoom+0.0008,1.25)':d={VIDEO_DUR*VIDEO_FPS}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s=2160x3840:fps={VIDEO_FPS}[zoomed_high];"
        
        # Step 3: Downscale back to 1080x1920 using Lanczos for flawless supersampled results
        f"[zoomed_high]scale=1080:1920:flags=lanczos[zoomed];"

        # Dark overlay (subtle 35-45% for high visibility of cinematic background)
        f"color=c={bg_color}:s=1080x1920:r={VIDEO_FPS}[bg];"
        f"[bg][zoomed]blend=all_mode=overlay:all_opacity={overlay_alpha}[blended];"

        # PHASE 1: Hook text (0-8s)
        f"[blended]drawtext=fontfile={FONT_PATH}:"
        f"textfile='{hook_file_str}':"
        f"fontcolor=white:fontsize=52:box=1:boxcolor=black@0.65:boxborderw=20:"
        f"x=(w-text_w)/2:y=h*0.15:enable='between(t,0,8)':"
        f"line_spacing=12[v1];"

        # PHASE 2: Reveal text with accent flash (8-15s)
        f"[v1]drawtext=fontfile={FONT_PATH}:"
        f"textfile='{reveal_file_str}':"
        f"fontcolor={accent_color}:fontsize=72:box=1:boxcolor=black@0.85:boxborderw=25:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,8,15)':"
        f"line_spacing=14[v2];"

        # PHASE 3: Pearl at bottom (15-20s)
        f"[v2]drawtext=fontfile={FONT_PATH}:"
        f"textfile='{pearl_file_str}':"
        f"fontcolor=white:fontsize=44:box=1:boxcolor={accent_color}@0.9:boxborderw=18:"
        f"x=(w-text_w)/2:y=h*0.78:enable='between(t,15,20)':"
        f"line_spacing=10[v3];"

        # DalilENT watermark (always visible)
        f"[v3]drawtext=fontfile={FONT_PATH}:"
        f"text='DalilENT':"
        f"fontcolor={accent_color}:fontsize=34:alpha=0.8:"
        f"x=w-text_w-30:y=h-text_h-30[vout]"
    )

    cmd = [
        'ffmpeg', '-y',
        '-loop', '1', '-i', str(image_path),
        '-filter_complex', filter_complex,
        '-map', '[vout]',
        '-c:v', 'libx264', '-preset', 'fast',
        '-t', str(VIDEO_DUR),
        '-r', str(VIDEO_FPS),
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        str(output_path)
    ]

    log(f"  🎞️  Running FFmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    # Cleanup temporary text files
    for f in [hook_file, reveal_file, pearl_file]:
        if f.exists():
            f.unlink()

    # Save FFmpeg log
    with open(LOG_DIR / f'ffmpeg_job_{job_id}.log', 'w') as f:
        f.write(result.stderr)

    if result.returncode != 0:
        log(f"  ❌ FFmpeg failed (exit {result.returncode})")
        log(f"  STDERR: {result.stderr[-500:]}")
        return False

    size_mb = output_path.stat().st_size / 1024 / 1024
    log(f"  ✅ Video rendered: {output_path.name} ({size_mb:.1f} MB)")
    return True


def upload_video(job_id, video_path):
    """Upload the rendered video to WordPress via REST API."""
    log(f"  📤 Uploading video to WordPress...")

    with open(video_path, 'rb') as f:
        video_bytes = f.read()

    video_b64 = base64.b64encode(video_bytes).decode('utf-8')
    filename   = f"reel_{job_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.mp4"

    url = f"{WP_SITE_URL}/wp-json/dme/v1/upload-video"
    payload = {
        'job_id':       job_id,
        'video_base64': video_b64,
        'filename':     filename
    }

    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        video_url = data.get('video_url', '')
        log(f"  ✅ Upload successful: {video_url}")
        return True
    except Exception as e:
        log(f"  ❌ Upload failed: {e}")
        return False


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("🎬 DalilENT Media Engine — GitHub Actions Renderer")
    log(f"🌐 Target: {WP_SITE_URL}")
    log("=" * 60)

    if not WP_SITE_URL or not WP_DME_TOKEN:
        log("❌ ERROR: WP_SITE_URL and WP_DME_TOKEN secrets are required!")
        sys.exit(1)

    # Secure Diagnostic Verification
    token_len = len(WP_DME_TOKEN)
    masked_token = f"{WP_DME_TOKEN[0]}...{WP_DME_TOKEN[-1]}" if token_len > 2 else "N/A"
    log(f"🔑 Token Secret Diagnostic: Length = {token_len} | Masked = '{masked_token}'")

    jobs = fetch_pending_jobs()
    log(f"📋 Found {len(jobs)} pending job(s).")

    if not jobs:
        log("✅ No jobs to process. Exiting.")
        sys.exit(0)

    success_count = 0
    fail_count    = 0

    for job in jobs:
        job_id   = job['job_id']
        title    = job['disease_title']
        script   = job.get('script', {})
        style    = job.get('style', 'dark_emergency')
        img_url  = job.get('thumbnail_url', '')

        log(f"\n{'─'*50}")
        log(f"🔄 Processing Job #{job_id}: {title}")
        log(f"   Style: {style} | Viral Score: {job.get('viral_score', '?')}/100")
        log(f"   Hook: {script.get('hook', 'N/A')[:60]}...")

        # Download image
        img_path = WORK_DIR / f"img_{job_id}.jpg"
        if img_url:
            # Recover the high-resolution original image if it's a WordPress thumbnail
            high_res_url = get_original_wp_image_url(img_url)
            log(f"  📥 High-res Image Check: {high_res_url}")
            if not download_image(high_res_url, img_path):
                log("  ⚠️  Failed to download high-res image, falling back to original thumbnail...")
                if not download_image(img_url, img_path):
                    # Use a generated placeholder background
                    log("  ⚠️  Using dark background fallback (no image)")
                    img_url = None
        
        if not img_url or not img_path.exists():
            # Create a solid dark background image with Pillow
            try:
                from PIL import Image, ImageDraw
                colors = {
                    'dark_emergency': (15, 15, 26),
                    'premium_academic': (26, 26, 46),
                    'viral_quiz': (15, 23, 42),
                }
                bg_rgb = colors.get(style, (15, 15, 26))
                img = Image.new('RGB', (VIDEO_W * 2, VIDEO_H * 2), color=bg_rgb)
                img.save(img_path, 'JPEG', quality=95)
                log(f"  🎨 Created placeholder background image")
            except Exception as e:
                log(f"  ❌ Could not create image: {e}")
                fail_count += 1
                continue

        # Render video
        output_path = WORK_DIR / f"reel_{job_id}.mp4"
        if not render_video(job_id, img_path, script, style, output_path):
            fail_count += 1
            continue

        # Upload to WordPress
        if upload_video(job_id, output_path):
            success_count += 1
        else:
            fail_count += 1

        # Cleanup local files
        for f in [img_path, output_path]:
            if f.exists():
                f.unlink()

    log(f"\n{'='*60}")
    log(f"🏁 Rendering Complete!")
    log(f"   ✅ Success: {success_count}")
    log(f"   ❌ Failed:  {fail_count}")
    log(f"{'='*60}")

    if fail_count > 0 and success_count == 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
