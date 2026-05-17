# 🎬 DalilENT Media Engine — GitHub Actions Renderer

Free video rendering pipeline for DalilENT WordPress plugin using GitHub Actions + FFmpeg.

## How It Works

```
WordPress (AI Script) → REST API → GitHub Actions (FFmpeg) → Upload Video → WordPress
```

1. **WordPress** generates cinematic scripts via OpenRouter/Gemini AI
2. **This repo** fetches pending jobs every 30 minutes via WordPress REST API
3. **FFmpeg** renders a professional 1080x1920 vertical video with zoom/pan + subtitles
4. **Rendered video** is uploaded back to WordPress automatically

## ⚙️ Setup (5 minutes)

### Step 1 — Fork or create this repo on GitHub

Upload the contents of the `github-actions/` folder from the plugin directory.

### Step 2 — Add GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Value |
|-------------|-------|
| `WP_SITE_URL` | `https://dalilent.com` |
| `WP_DME_TOKEN` | The token you generated in WordPress DME Settings |

### Step 3 — Configure WordPress

In WordPress admin → **DalilENT Media** tab → **⚙️ الإعدادات**:

1. Generate a secret token using the "🎲 توليد تلقائي" button
2. Save settings
3. Copy the token value and paste it as `WP_DME_TOKEN` in GitHub Secrets
4. Copy your site URL and paste it as `WP_SITE_URL`

### Step 4 — Enable GitHub Actions

The workflow runs automatically every 30 minutes. You can also trigger it manually:
- Go to **Actions** tab → **🎬 DalilENT Reel Renderer** → **Run workflow**

## 📁 Repository Structure

```
├── .github/
│   └── workflows/
│       └── render-reels.yml    ← GitHub Actions workflow
├── render_reels.py              ← Main render script (Python + FFmpeg)
└── README.md
```

## 🎨 Video Specs

| Setting | Value |
|---------|-------|
| Resolution | 1080 × 1920 (9:16 vertical) |
| Duration | 20 seconds |
| FPS | 30 |
| Format | H.264 MP4 |
| Effect | Slow zoom-pan (Ken Burns) |
| Subtitles | 3-phase cinematic reveal |

## 💡 Free Tier Limits

GitHub Actions Free Tier: **2,000 minutes/month**  
Each render job: ~2-3 minutes  
= **~700 videos/month for free** 🎉

## 🛠️ Troubleshooting

- **No jobs rendered**: Check that the `WP_DME_TOKEN` matches exactly what's saved in WordPress settings
- **FFmpeg error**: Check the render logs in GitHub Actions → Artifacts
- **Upload failed**: Verify `WP_SITE_URL` doesn't have a trailing slash and the REST API is accessible
