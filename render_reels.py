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

# Video specs — Cinematic Vertical 9:16 (True 4K Ultra HD)
VIDEO_W   = 2160
VIDEO_H   = 3840
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


def render_video(job_id, image_paths, script, style, output_path):
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

    # ─── Color Palette & Typography Design by Style (4K Resolution Specs) ─────
    if style == 'premium_academic':
        # Elegant Navy and Luxury Gold Look
        bg_color       = '0x0b0f19'
        accent_color   = '0xf59e0b'  # Gold
        overlay_alpha  = '0.35'
        
        # Phase 1 Subtitles: Sleek Navy Box with Gold Border Outline
        p1_fontcolor   = 'white'
        p1_fontsize    = 104  # 4K Double-scaled
        p1_boxcolor    = '0x0f172a@0.85'
        p1_boxborder   = 44   # 4K Double-scaled
        p1_borderw     = 4    # 4K Double-scaled
        p1_bordercolor = '0xf59e0b'
        
        # Phase 2 (Reveal): Magnificent Bold Gold Block with subtle dark shadow
        p2_fontcolor   = '0xf59e0b'
        p2_fontsize    = 148  # 4K Double-scaled
        p2_boxcolor    = '0x0b0f19@0.9'
        p2_boxborder   = 52   # 4K Double-scaled
        p2_borderw     = 0
        p2_bordercolor = 'black'
        
        # Phase 3 (Pearl): Slate Box with elegant Gold outline
        p3_fontcolor   = 'white'
        p3_fontsize    = 88   # 4K Double-scaled
        p3_boxcolor    = '0x1e293b@0.9'
        p3_boxborder   = 36   # 4K Double-scaled
        p3_borderw     = 4    # 4K Double-scaled
        p3_bordercolor = '0xf59e0b'
        
    elif style == 'viral_quiz':
        # High-retention Electric Purple & Cyan
        bg_color       = '0x0d071a'
        accent_color   = '0x8b5cf6'  # Purple
        overlay_alpha  = '0.40'
        
        # Phase 1 Subtitles: Cyber Purple Glow Box
        p1_fontcolor   = 'white'
        p1_fontsize    = 108  # 4K Double-scaled
        p1_boxcolor    = '0x1e1b4b@0.85'
        p1_boxborder   = 40   # 4K Double-scaled
        p1_borderw     = 4    # 4K Double-scaled
        p1_bordercolor = '0x8b5cf6'
        
        # Phase 2 (Reveal): Dynamic Cyber Cyan pop
        p2_fontcolor   = '0x06b6d4'  # Neon Cyan
        p2_fontsize    = 152  # 4K Double-scaled
        p2_boxcolor    = 'black@0.9'
        p2_boxborder   = 56   # 4K Double-scaled
        p2_borderw     = 4    # 4K Double-scaled
        p2_bordercolor = '0x06b6d4'
        
        # Phase 3 (Pearl): Deep Indigo Box with Neon Purple Border
        p3_fontcolor   = 'white'
        p3_fontsize    = 92   # 4K Double-scaled
        p3_boxcolor    = '0x311042@0.9'
        p3_boxborder   = 40   # 4K Double-scaled
        p3_borderw     = 4    # 4K Double-scaled
        p3_bordercolor = '0x8b5cf6'
        
    else:  # dark_emergency
        # High Stakes Dramatic Emergency
        bg_color       = '0x0d0306'  # Deep Crimson Black
        accent_color   = '0xe11d48'  # Neon Red
        overlay_alpha  = '0.45'
        
        # Phase 1 Subtitles: Deep Crimson Dark Box with warning outline
        p1_fontcolor   = 'white'
        p1_fontsize    = 104  # 4K Double-scaled
        p1_boxcolor    = '0x180206@0.85'
        p1_boxborder   = 44   # 4K Double-scaled
        p1_borderw     = 4    # 4K Double-scaled
        p1_bordercolor = '0xe11d48'
        
        # Phase 2 (Reveal): High contrast warning block
        p2_fontcolor   = '0xe11d48'
        p2_fontsize    = 144  # 4K Double-scaled
        p2_boxcolor    = 'black@0.9'
        p2_boxborder   = 50   # 4K Double-scaled
        p2_borderw     = 6    # 4K Double-scaled
        p2_bordercolor = '0xe11d48'
        
        # Phase 3 (Pearl): Solid Emergency Warning block
        p3_fontcolor   = 'white'
        p3_fontsize    = 88   # 4K Double-scaled
        p3_boxcolor    = '0xe11d48@0.95'
        p3_boxborder   = 36   # 4K Double-scaled
        p3_borderw     = 0
        p3_bordercolor = 'black'

    # ─── Build FFmpeg Filter Graph ────────────────────────────────────────────
    # Using textfile avoids any quoting or escaping issues in drawtext.
    # Paths must be passed with forward slashes to FFmpeg even on Windows.
    hook_file_str   = str(hook_file).replace('\\', '/')
    reveal_file_str = str(reveal_file).replace('\\', '/')
    pearl_file_str  = str(pearl_file).replace('\\', '/')

    # Calculate frames per segment for N images
    num_images = len(image_paths)
    seg_dur = VIDEO_DUR / num_images
    seg_frames = int(seg_dur * VIDEO_FPS)

    # Dynamic Filter Graph for multi-image slideshow (Pure 4K Ultra HD):
    # 1. Loop through all image inputs, scale to 4K using Lanczos.
    # 2. Run the zoompan filter on each input at full 2160x3840 resolution.
    # 3. Apply professional Hollywood dramatic vignette and vibrant brightness correction.
    # 4. Concatenate all segments sequentially without downscaling.
    filter_parts = []
    concat_inputs = ""
    for i, path in enumerate(image_paths):
        filter_parts.append(
            f"[{i}:v]scale=2160:3840:flags=lanczos,"
            f"zoompan=z='min(zoom+0.0008,1.25)':d={seg_frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s=2160x3840:fps={VIDEO_FPS},"
            f"vignette=PI/5,eq=contrast=1.08:saturation=1.22:brightness=0.04[v{i}_zoomed]"
        )
        concat_inputs += f"[v{i}_zoomed]"

    # Concatenate all zoomed clips
    filter_parts.append(f"{concat_inputs}concat=n={num_images}:v=1:a=0[zoomed]")

    filter_complex_str = ";".join(filter_parts)

    filter_complex = (
        filter_complex_str + ";"
        # PHASE 1: Hook text (0-8s) with elegant 0.5s fade-in & fade-out
        f"[zoomed]drawtext=fontfile={FONT_PATH}:"
        f"textfile='{hook_file_str}':"
        f"fontcolor={p1_fontcolor}:fontsize={p1_fontsize}:"
        f"box=1:boxcolor={p1_boxcolor}:boxborderw={p1_boxborder}:"
        f"borderw={p1_borderw}:bordercolor={p1_bordercolor}:"
        f"x=(w-text_w)/2:y=h*0.15:enable='between(t,0,8)':"
        f"alpha='if(lt(t,0.5),2*t,if(gt(t,7.5),2*(8-t),1))':"
        f"line_spacing=24[v1];"

        # PHASE 2: Reveal text with accent flash (8-15s) with elegant 0.5s fade-in & fade-out
        f"[v1]drawtext=fontfile={FONT_PATH}:"
        f"textfile='{reveal_file_str}':"
        f"fontcolor={p2_fontcolor}:fontsize={p2_fontsize}:"
        f"box=1:boxcolor={p2_boxcolor}:boxborderw={p2_boxborder}:"
        f"borderw={p2_borderw}:bordercolor={p2_bordercolor}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,8,15)':"
        f"alpha='if(lt(t,8.5),2*(t-8),if(gt(t,14.5),2*(15-t),1))':"
        f"line_spacing=28[v2];"

        # PHASE 3: Pearl at bottom (15-20s) with elegant 0.5s fade-in & fade-out
        f"[v2]drawtext=fontfile={FONT_PATH}:"
        f"textfile='{pearl_file_str}':"
        f"fontcolor={p3_fontcolor}:fontsize={p3_fontsize}:"
        f"box=1:boxcolor={p3_boxcolor}:boxborderw={p3_boxborder}:"
        f"borderw={p3_borderw}:bordercolor={p3_bordercolor}:"
        f"x=(w-text_w)/2:y=h*0.78:enable='between(t,15,20)':"
        f"alpha='if(lt(t,15.5),2*(t-15),if(gt(t,19.5),2*(20-t),1))':"
        f"line_spacing=20[v3];"

        # DalilENT watermark (always visible)
        f"[v3]drawtext=fontfile={FONT_PATH}:"
        f"text='DalilENT':"
        f"fontcolor={accent_color}:fontsize=68:alpha=0.85:"
        f"x=w-text_w-60:y=h-text_h-60[vout]"
    )

    # Compile FFmpeg Command with multiple inputs
    cmd = ['ffmpeg', '-y']
    for path in image_paths:
        cmd.extend(['-loop', '1', '-t', f"{seg_dur:.2f}", '-i', str(path)])

    cmd.extend([
        '-filter_complex', filter_complex,
        '-map', '[vout]',
        '-c:v', 'libx264', '-preset', 'fast',
        '-t', str(VIDEO_DUR),
        '-r', str(VIDEO_FPS),
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        str(output_path)
    ])

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

        # Download images
        additional_images = job.get('additional_images', [])
        if not additional_images and img_url:
            additional_images = [img_url]

        downloaded_images = []
        for i, url in enumerate(additional_images):
            img_path = WORK_DIR / f"img_{job_id}_{i}.jpg"
            high_res_url = get_original_wp_image_url(url)
            log(f"  📥 Image [{i}] High-res Check: {high_res_url}")
            if download_image(high_res_url, img_path):
                downloaded_images.append(img_path)
            elif download_image(url, img_path):
                downloaded_images.append(img_path)
            else:
                log(f"  ⚠️  Failed to download image [{i}]")

        # Fallback if no images were successfully downloaded
        if not downloaded_images:
            img_path = WORK_DIR / f"img_{job_id}_fallback.jpg"
            try:
                from PIL import Image
                colors = {
                    'dark_emergency': (15, 15, 26),
                    'premium_academic': (26, 26, 46),
                    'viral_quiz': (15, 23, 42),
                }
                bg_rgb = colors.get(style, (15, 15, 26))
                img = Image.new('RGB', (VIDEO_W * 2, VIDEO_H * 2), color=bg_rgb)
                img.save(img_path, 'JPEG', quality=95)
                downloaded_images.append(img_path)
                log(f"  🎨 Created placeholder background image")
            except Exception as e:
                log(f"  ❌ Could not create fallback image: {e}")
                fail_count += 1
                continue

        # Render video
        output_path = WORK_DIR / f"reel_{job_id}.mp4"
        if not render_video(job_id, downloaded_images, script, style, output_path):
            # Cleanup downloaded images
            for f in downloaded_images:
                if f.exists():
                    f.unlink()
            fail_count += 1
            continue

        # Upload to WordPress
        if upload_video(job_id, output_path):
            success_count += 1
        else:
            fail_count += 1

        # Cleanup local files
        for f in downloaded_images + [output_path]:
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
