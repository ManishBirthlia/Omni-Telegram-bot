# 🎨 KidsToon AI — Fully Automated AI Kids Cartoon Generator & YouTube Publisher

> **A production-grade Telegram bot that transforms a single topic prompt into a fully produced, uploaded kids cartoon video on YouTube — zero manual intervention required.**

---

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [How It Works](#how-it-works)
- [Bot Commands](#bot-commands)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [API Keys & Services Required](#api-keys--services-required)
- [YouTube & COPPA Compliance](#youtube--coppa-compliance)
- [Deployment](#deployment)
- [Scaling Strategy](#scaling-strategy)
- [Monitoring & Observability](#monitoring--observability)
- [Common Issues & Troubleshooting](#common-issues--troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Project Overview

**KidsToon AI** is a fully automated content factory for kids YouTube channels. You send a topic via Telegram — for example, *"Counting Animals 1 to 10"* — and the bot handles everything:

- Writes a child-appropriate script using Claude AI
- Generates consistent cartoon-style images for each scene using DALL-E 3
- Converts images into animated video clips using Runway ML (or Google Veo when available)
- Generates a natural-sounding AI voiceover using ElevenLabs
- Adds royalty-free background music     
- Assembles all scenes into a final video using FFmpeg
- Auto-generates SEO-optimized title, description, tags, and chapters
- Creates a vibrant, click-worthy thumbnail
- Uploads to your YouTube channel with proper Kids/COPPA settings
- Notifies you via Telegram with the live YouTube link

**Zero copyright risk. 100% original content. Fully automated.**

---

## ✨ Key Features

- **Multi-channel support** — manage multiple YouTube channels from one bot instance
- **Character consistency engine** — AI characters look the same across every scene in a video
- **Smart scheduling** — uploads at peak engagement hours, respects YouTube API quota limits
- **COPPA-compliant uploads** — automatically marks content as "Made for Kids"
- **Quota budget manager** — tracks YouTube API usage and prevents quota exhaustion
- **Full observability** — every pipeline stage is traced, logged, and alerted
- **Idempotent pipeline** — safe retries at every stage; failed jobs resume where they left off
- **Dead letter queue** — failed jobs are preserved for manual inspection and requeue
- **Series support** — generate a full 10-episode series from one command
- **Multi-language voiceover** — generate the same video in multiple languages for international reach

---

## 🏗 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     TELEGRAM BOT LAYER                      │
│              Aiogram 3.x  |  FSM  |  Middleware             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   TASK ORCHESTRATION LAYER                  │
│         Celery + Redis  |  4 Separate Worker Queues         │
└──────┬──────────────────┬──────────────────┬────────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌──────────────┐  ┌───────────────┐  ┌─────────────────┐
│  INTELLIGENCE│  │   GENERATION  │  │    ASSEMBLY     │
│    LAYER     │  │     LAYER     │  │     LAYER       │
│              │  │               │  │                 │
│ Claude API   │  │ DALL-E 3      │  │ FFmpeg Pipeline │
│ Script Gen   │  │ Runway ML     │  │ Scene Assembly  │
│ Metadata Gen │  │ ElevenLabs    │  │ Audio Mix       │
│ Whisper      │  │ MusicGen      │  │ Subtitle Burn   │
└──────────────┘  └───────────────┘  └────────┬────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      OUTPUT LAYER                           │
│     YouTube Data API v3  |  Quota Manager  |  Scheduler     │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                     │
│   PostgreSQL  |  Redis  |  S3/R2  |  Docker  |  Kubernetes  │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Prerequisites

- Python 3.11+
- Docker & Docker Compose
- FFmpeg 6.0+ installed on host
- Node.js 18+ (for thumbnail compositor)
- GPU recommended for Whisper inference (CPU works but is slower)
- Minimum 8GB RAM, 4 vCPU for production
- 50GB SSD storage for video processing temp files

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourname/kidstoon-ai.git
cd kidstoon-ai
```

### 2. Install uv (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Create Virtual Environment & Install Dependencies

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 4. Install FFmpeg

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y ffmpeg

# macOS
brew install ffmpeg

# Verify
ffmpeg -version
```

### 5. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env with your API keys (see Configuration section)
```

### 6. Initialize the Database

```bash
alembic upgrade head
```

### 7. Start All Services with Docker Compose

```bash
docker-compose up -d
```

---

## 🔧 Configuration

Copy `.env.example` to `.env` and fill in all values:

```env
# ── Telegram ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ADMIN_CHAT_ID=your_personal_chat_id

# ── AI Services ───────────────────────────────────────────
ANTHROPIC_API_KEY=your_claude_api_key
OPENAI_API_KEY=your_openai_key_for_dalle3_and_whisper
ELEVENLABS_API_KEY=your_elevenlabs_key
ELEVENLABS_VOICE_ID=voice_id_for_kids_narration

# ── Video Generation ──────────────────────────────────────
RUNWAY_API_KEY=your_runway_ml_key
GOOGLE_VEO_API_KEY=your_veo_key_if_available

# ── YouTube ───────────────────────────────────────────────
YOUTUBE_CLIENT_ID=your_oauth_client_id
YOUTUBE_CLIENT_SECRET=your_oauth_client_secret
YOUTUBE_REFRESH_TOKEN=your_refresh_token
YOUTUBE_CHANNEL_ID=your_channel_id
YOUTUBE_DAILY_QUOTA_LIMIT=10000
YOUTUBE_QUOTA_SAFETY_BUFFER=2000

# ── Infrastructure ────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://user:password@localhost/kidstoon
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
S3_BUCKET_NAME=kidstoon-processing
S3_REGION=us-east-1

# ── App Settings ──────────────────────────────────────────
MAX_CONCURRENT_JOBS=3
DEFAULT_VIDEO_DURATION_TARGET=180
UPLOAD_SCHEDULE_HOUR=14
ENVIRONMENT=production
LOG_LEVEL=INFO

# ── Observability ─────────────────────────────────────────
SENTRY_DSN=your_sentry_dsn
PROMETHEUS_PORT=9090
```

---

## ▶️ Running the Application

### Development

```bash
# Start infrastructure (Redis, PostgreSQL)
docker-compose up -d redis postgres

# Run bot
python -m bot.main

# Run Celery workers (separate terminals)
celery -A workers.celery_app worker -Q intelligence --concurrency=4 -n intelligence@%h
celery -A workers.celery_app worker -Q generation --concurrency=2 -n generation@%h
celery -A workers.celery_app worker -Q assembly --concurrency=2 -n assembly@%h
celery -A workers.celery_app worker -Q upload --concurrency=3 -n upload@%h

# Run Celery Beat (scheduler)
celery -A workers.celery_app beat --loglevel=info
```

### Production (Docker Compose)

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Production (Kubernetes)

```bash
kubectl apply -f k8s/
```

---

## 🎬 How It Works

### Single Video Generation

1. Send `/generate` to the bot
2. Bot asks for a topic (e.g., "Shapes and Colors for Toddlers")
3. Optionally configure: duration target, art style, voiceover language, publish time
4. Bot confirms and queues the job
5. Bot sends live progress updates as each pipeline stage completes
6. Final message includes the YouTube link, video stats, and a preview thumbnail

### Series Generation

1. Send `/series` to the bot
2. Provide a series theme (e.g., "Animals of the Jungle — 10 episodes")
3. Claude generates episode titles and scripts for the full series
4. All episodes are queued and processed sequentially or in parallel
5. Each episode is uploaded with consistent series branding and playlist assignment

---

## 🤖 Bot Commands

| Command | Description |
|---|---|
| `/start` | Initialize the bot and authenticate |
| `/generate` | Start a new single video generation |
| `/series` | Generate a multi-episode series |
| `/status` | Check status of all running jobs |
| `/queue` | View pending job queue |
| `/quota` | Check today's remaining YouTube API quota |
| `/schedule` | View and manage scheduled uploads |
| `/channels` | Manage connected YouTube channels |
| `/styles` | View available art styles (cartoon, watercolor, flat design) |
| `/voices` | Preview available AI voiceover options |
| `/cancel [job_id]` | Cancel a running or queued job |
| `/history` | View last 10 completed jobs with YouTube links |
| `/settings` | Configure default preferences |
| `/help` | Show all commands and usage |

---

## 📁 Project Structure

```
kidstoon-ai/
├── bot/
│   ├── main.py                    # Aiogram app entry point
│   ├── handlers/
│   │   ├── generate.py            # /generate command handler
│   │   ├── series.py              # /series command handler
│   │   ├── status.py              # Job status handlers
│   │   └── settings.py            # User settings handlers
│   ├── middlewares/
│   │   ├── rate_limiter.py        # Per-user rate limiting
│   │   ├── auth.py                # User authentication
│   │   └── logger.py              # Request logging middleware
│   ├── fsm/
│   │   └── states.py              # FSM state definitions
│   └── keyboards/
│       └── inline.py              # Telegram inline keyboards
│
├── pipeline/
│   ├── intelligence/
│   │   ├── script_generator.py    # Claude API script generation
│   │   ├── metadata_generator.py  # SEO metadata generation
│   │   └── topic_expander.py      # Series topic expansion
│   ├── generation/
│   │   ├── image_generator.py     # DALL-E 3 image generation
│   │   ├── character_engine.py    # Character consistency manager
│   │   ├── video_generator.py     # Runway ML / Veo API wrapper
│   │   ├── voiceover.py           # ElevenLabs TTS
│   │   └── music_selector.py      # Royalty-free music selection
│   ├── assembly/
│   │   ├── video_pipeline.py      # FFmpeg pipeline builder
│   │   ├── scene_assembler.py     # Scene-by-scene assembly
│   │   ├── audio_mixer.py         # Voice + music mixing
│   │   └── thumbnail_compositor.py # Thumbnail generation
│   └── upload/
│       ├── youtube_uploader.py    # YouTube Data API v3
│       ├── quota_manager.py       # API quota tracking
│       └── scheduler.py           # Upload scheduling
│
├── workers/
│   ├── celery_app.py              # Celery configuration
│   ├── intelligence_tasks.py      # Intelligence queue tasks
│   ├── generation_tasks.py        # Generation queue tasks
│   ├── assembly_tasks.py          # Assembly queue tasks
│   └── upload_tasks.py            # Upload queue tasks
│
├── models/
│   ├── pipeline_job.py            # Job state machine model
│   ├── quota_usage.py             # Quota tracking model
│   ├── channel.py                 # YouTube channel model
│   └── user.py                    # Telegram user model
│
├── storage/
│   ├── s3_client.py               # AWS S3 / Cloudflare R2 client
│   └── local_cache.py             # Local temp file management
│
├── observability/
│   ├── tracing.py                 # OpenTelemetry setup
│   ├── metrics.py                 # Prometheus metrics
│   └── alerts.py                  # Alert rules
│
├── migrations/                    # Alembic migrations
├── k8s/                           # Kubernetes manifests
├── docker-compose.yml
├── docker-compose.prod.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔑 API Keys & Services Required

| Service | Purpose | Free Tier | Estimated Cost at Scale |
|---|---|---|---|
| Telegram BotFather | Bot token | Free | Free |
| Anthropic Claude | Script + metadata generation | $5 credit | ~$0.02/video |
| OpenAI (DALL-E 3) | Image generation | $5 credit | ~$0.20/video (8 images) |
| ElevenLabs | AI voiceover | 10k chars/mo | ~$0.10/video |
| Runway ML Gen-3 | Image-to-video | 125 credits trial | ~$0.50/video |
| YouTube Data API | Video upload | 10k units/day | Free (apply for more) |
| AWS S3 / CF R2 | Temp file storage | 5GB free | ~$0.02/video |
| Sentry | Error tracking | 5k errors/mo | Free for small scale |

**Estimated total cost per video: ~$0.85–$1.20**
At 5 videos/day: ~$150/month in API costs
YouTube AdSense CPM for kids content: $1–$4 per 1,000 views
Break-even: ~50,000 views/month across your channel

---

## 👶 YouTube & COPPA Compliance

This application is designed for children's content. The following compliance measures are implemented by default:

- All videos uploaded with `madeForKids: true` in the YouTube API call
- No personal data collected from viewers
- Comment sections disabled automatically (YouTube enforces this for kids content)
- No personalized advertising (YouTube enforces this for kids content)
- Age-appropriate content validation in the script generation prompt
- No external links embedded in video descriptions targeting children

**Important:** You are responsible for ensuring your content complies with COPPA, the YouTube Terms of Service, and YouTube's policies for content made for children. Review [YouTube's Made for Kids guidelines](https://support.google.com/youtube/answer/9527654) before launching.

---

## 🐳 Deployment

### Option A: Single VPS (Getting Started)

Recommended: DigitalOcean Droplet — 4 vCPU, 8GB RAM, 160GB SSD (~$48/month)

```bash
# On your VPS
git clone https://github.com/yourname/kidstoon-ai.git
cd kidstoon-ai
cp .env.example .env && nano .env
docker-compose -f docker-compose.prod.yml up -d
```

### Option B: Kubernetes (Production Scale)

```bash
# Set up cluster (DigitalOcean Kubernetes recommended)
doctl kubernetes cluster create kidstoon-cluster \
  --node-pool "name=workers;size=s-4vcpu-8gb;count=2"

# Deploy
kubectl apply -f k8s/namespace.yml
kubectl apply -f k8s/secrets.yml
kubectl apply -f k8s/deployments/
kubectl apply -f k8s/services/
kubectl apply -f k8s/hpa/  # Horizontal Pod Autoscaler
```

### GPU Node for Whisper (Optional but Recommended)

```bash
# Add GPU node pool for faster transcription
doctl kubernetes node-pool create kidstoon-cluster \
  --name gpu-workers \
  --size s-4vcpu-8gb-amd \
  --count 1
```

---

## 📈 Scaling Strategy

The system is designed to scale each layer independently:

- **Intelligence workers** scale with Claude/OpenAI API rate limits (scale horizontally)
- **Generation workers** scale with Runway ML credit availability (scale horizontally)
- **Assembly workers** scale with CPU/GPU availability (scale vertically first)
- **Upload workers** are quota-bound — scaling them doesn't help until quota increases

When queue depth exceeds 10 jobs on any queue, Kubernetes HPA automatically adds worker pods. When queue depth drops to 0 for 10 minutes, excess pods are terminated.

---

## 📊 Monitoring & Observability

Access dashboards:
- **Grafana** — `http://your-server:3000` — pipeline metrics, queue depths, quota usage
- **Flower** — `http://your-server:5555` — Celery task monitoring
- **Prometheus** — `http://your-server:9090` — raw metrics

Key alerts configured out of the box:
- YouTube quota below 2,000 units → Telegram alert to admin
- Job failure rate > 10% in 1 hour → Telegram alert
- Assembly worker CPU > 90% for 5 minutes → auto-scale trigger
- Dead letter queue depth > 5 → Telegram alert

---

## 🐛 Common Issues & Troubleshooting

**"YouTube quota exceeded" error**
The bot will automatically pause uploads and resume after midnight Pacific Time when quota resets. You can check remaining quota with `/quota` in Telegram.

**Character looks different between scenes**
Increase the `CHARACTER_CONSISTENCY_STRENGTH` env variable (0.0–1.0). Default is 0.7. Higher values maintain consistency but reduce scene variety.

**Runway ML video generation fails**
Runway Gen-3 occasionally fails on complex prompts. The pipeline automatically retries with a simplified prompt. Check the job logs for the simplified prompt that was used.

**FFmpeg process killed (OOM)**
Increase the assembly worker container memory limit. 4K video assembly requires up to 6GB RAM. For standard 1080p kids content, 3GB is sufficient.

**ElevenLabs voice sounds unnatural**
Try the `eleven_turbo_v2_5` model instead of the default. Adjust `stability` (0.5) and `similarity_boost` (0.75) settings in your `.env`.

---

## 🗺 Roadmap

- [ ] **v1.0** — Core pipeline: script → image → video → voice → upload
- [ ] **v1.1** — Character consistency via LoRA fine-tuning
- [ ] **v1.2** — Series management with playlist auto-creation
- [ ] **v1.3** — Multi-language voiceover (Hindi, Spanish, French)
- [ ] **v1.4** — Analytics dashboard (views, revenue estimates, CTR)
- [ ] **v2.0** — Multi-platform distribution (extend to YouTube Shorts auto-clips)
- [ ] **v2.1** — Web dashboard UI (remove Telegram dependency for power users)
- [ ] **v2.2** — Google Veo integration (when API becomes generally available)
- [ ] **v3.0** — SaaS multi-tenant mode with per-client billing

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built with Python 3.11, Aiogram, Celery, FFmpeg, Claude AI, DALL-E 3, Runway ML, ElevenLabs, and the YouTube Data API v3.*
