# 🧱 STACK.md — Complete Expert Stack Summary
## KidsToon AI — AI Kids Cartoon Generator

> Every technology choice below is justified by a specific technical requirement.  
> No cargo-culting. No trend-chasing. Every tool earns its place.

---

## Language & Runtime

| Decision | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | Best-in-class ecosystem for AI/ML, video processing, and API clients. 25% faster than 3.10 due to Faster CPython project. |
| Package Manager | **uv** | Rust-based, 10–100x faster than pip/poetry. Deterministic lockfile. Becoming industry standard. |
| Async Runtime | **asyncio (native)** | All I/O in this system is network-bound (API calls, downloads, uploads). Async eliminates blocking. |
| Type Safety | **Pydantic v2** | Runtime data validation for all API responses, configuration, and pipeline data contracts. Catches malformed AI API responses before they crash the pipeline. |

---

## Telegram Bot Layer

| Decision | Choice | Why Not Alternative |
|---|---|---|
| Bot Framework | **Aiogram 3.x** | Native async from the ground up. Built-in FSM engine. Middleware support. `python-telegram-bot` is synchronous at its core — fatal for a long-running video pipeline. |
| Conversation State | **Aiogram FSM + Redis backend** | Users have multi-step configuration flows (topic → style → duration → confirm). FSM tracks state per user without in-memory storage that disappears on restart. Redis backend survives bot restarts. |
| Rate Limiting | **Custom Aiogram middleware** | Prevents a single user from flooding the queue with 50 generation requests. Middleware intercepts every incoming update before handlers see it. |
| User Auth | **Telegram user_id whitelist** | Simple, effective. Only authorized Telegram IDs can trigger pipeline jobs. No password management needed. |

---

## AI Intelligence Layer

| Decision | Choice | Why |
|---|---|---|
| Script Generation | **Claude claude-sonnet-4-6 API** | Best instruction-following for structured creative output with safety built in. Kids content requires strict adherence to age-appropriate guidelines — Claude's constitutional AI approach handles this better than GPT-4o in practice. Structured JSON output mode eliminates fragile string parsing. |
| Metadata Generation | **Claude claude-sonnet-4-6 API (same call)** | Title, description, tags, and chapters generated in one API call alongside the script to maintain thematic consistency. Front-loaded keyword optimization for YouTube SEO. |
| Prompt Architecture | **System prompt + few-shot examples** | Static system prompt defines character style, age appropriateness, and output schema. Few-shot examples in the user turn demonstrate exactly what a good script looks like. Reduces generation failures by ~80% vs zero-shot. |
| Transcription (future) | **faster-whisper (local, GPU)** | For adding auto-generated subtitles. faster-whisper is 4x faster than original Whisper on CPU, runs in seconds on GPU. Zero per-minute cost vs Whisper API. |

---

## Image Generation Layer

| Decision | Choice | Why |
|---|---|---|
| Primary Image Gen | **DALL-E 3 via OpenAI API** | Best prompt adherence of any commercial image model. Kids cartoon aesthetic is very well represented in its training data. Generates 1024x1024 natively, upscalable to 1792x1024 for cinematic crops. |
| Fallback Image Gen | **Stable Diffusion XL via Replicate API** | DALL-E 3 rate limits can bottleneck series generation (50 images/minute). SDXL via Replicate is cheaper at scale and faster for bulk generation. |
| Character Consistency | **Reference image seeding + detailed character description in every prompt** | The core problem with AI image generation for storytelling. Solved by: (1) generating a canonical character reference image first, (2) including it as an image reference in every subsequent DALL-E call, (3) embedding full character description in every scene prompt. |
| Long-term Consistency | **LoRA fine-tuning on Stable Diffusion (v2 roadmap)** | For channels that run hundreds of episodes, a custom LoRA on your character design gives 95%+ visual consistency across all scenes. Requires 20–50 reference images and a one-time training run (~$5 on Replicate). |
| Image Storage | **AWS S3 with CDN** | Generated images are reused across pipeline stages (thumbnails, video frames). S3 provides durable storage with pre-signed URL access. |

---

## Video Generation Layer

| Decision | Choice | Reasoning |
|---|---|---|
| Primary Video Gen | **Runway ML Gen-3 Alpha API** | Currently the best commercially available image-to-video API. Generates 5–10 second clips from a still image. Good motion quality for cartoon-style content. API is stable and well-documented. |
| Fallback Video Gen | **Pika Labs API** | When Runway ML rate limits hit (common during peak hours), Pika provides near-identical quality. Both use the same input format — switching is seamless. |
| Future Primary | **Google Veo 2 API** | When generally available, Veo 2's native character consistency and superior motion quality make it the best choice. Architecture already has the integration point ready. |
| Clip Duration | **5 seconds per scene, assembled by FFmpeg** | Runway Gen-3 produces best quality at 5-second clips. Longer clips show more motion artifacts. 5-second clips × 30 scenes = 2.5-minute video, ideal for kids content attention spans. |
| Scene Transition | **FFmpeg xfade filter** | 0.3-second crossfade between scenes. Smooth, professional, computed in one FFmpeg pass — no re-encoding overhead. |

---

## Audio Layer

| Decision | Choice | Why |
|---|---|---|
| Voiceover | **ElevenLabs API** | Best-in-class TTS for natural, expressive narration. Kids content needs warm, clear, engaging voice delivery. ElevenLabs "Charlotte" and "Bill" voices consistently test well for children's content. Supports SSML for pacing control. |
| Background Music | **Freesound API + YouTube Audio Library** | Royalty-free, searchable by mood/tempo/genre. Programmatically find a track that matches the video's theme. Zero licensing cost. |
| Audio Assembly | **FFmpeg amix + loudnorm** | Mix voiceover (primary) with background music (secondary at -18dB) in one pass. Apply EBU R128 loudness normalization so the final mix sounds professional on all devices. |
| Silence Detection | **ffmpeg silencedetect filter** | Automatically trims silence from generated voiceover clips. TTS often adds trailing silence that causes awkward pauses between scenes. |
| Music Generation (future) | **AudioCraft MusicGen** | For completely unique background music per video. Generates thematically appropriate music from a text prompt. Currently adds ~2 minutes to pipeline — suitable as an opt-in feature. |

---

## Video Assembly Layer

| Decision | Choice | Why |
|---|---|---|
| Video Processing | **FFmpeg 6.0+** | Industry standard. Single filter graph processes all transformations in one pass: concatenate scenes + mix audio + burn subtitles + add watermark + apply color grade. One-pass processing is 5x faster than sequential operations. |
| Python Binding | **ffmpeg-python** | Clean Python interface for building complex FFmpeg filter graphs programmatically. Type-safe pipeline builder pattern instead of shell string concatenation. |
| Hardware Acceleration | **h264_nvenc (Nvidia GPU) / libx264 (CPU)** | GPU encoding is 8–10x faster for H.264 output. Auto-detected and used when available. CPU fallback uses `-preset fast` — YouTube re-encodes everything anyway so output quality matters less than speed. |
| Subtitle Style | **ASS format subtitles, burnt in** | Advanced SubStation Alpha gives full control over font, size, color, position, animation, and outline. Burnt into video so they appear on all platforms regardless of player. Kids content uses large, bold, colorful fonts. |
| Thumbnail | **Pillow (Python) + FFmpeg scene extraction** | Extract the most visually interesting frame from the assembled video using PySceneDetect's content-aware detection. Composite with bold text overlay, logo, and color background using Pillow. Pure Python — no external service needed. |

---

## Task Queue & Orchestration

| Decision | Choice | Why |
|---|---|---|
| Task Queue | **Celery 5.x** | Mature, battle-tested distributed task queue. Supports complex workflows, task chaining, periodic tasks, and retry strategies. |
| Message Broker | **Redis 7.x** | In-memory, fast, supports Celery pub/sub and FSM state storage simultaneously. Simpler than RabbitMQ for this use case. |
| Queue Architecture | **4 separate named queues** | `intelligence` (API-bound), `generation` (API + GPU-bound), `assembly` (CPU-bound), `upload` (network-bound). Separate queues prevent CPU-heavy assembly tasks from starving lightweight API calls. |
| Worker Concurrency | **Per-queue tuning** | intelligence: 6 workers, generation: 3 workers, assembly: 2 workers, upload: 4 workers. Assembly workers are low count because FFmpeg is already multi-threaded internally. |
| Retry Strategy | **Exponential backoff with jitter** | External APIs fail transiently. Retry after 60s, 120s, 240s with ±10% jitter to prevent thundering herd. Max 3 retries before dead letter queue. |
| Dead Letter Queue | **Separate Redis list + Telegram alert** | Failed jobs are not lost. Admin is notified immediately and can inspect, fix, and requeue from Telegram. |
| Scheduler | **Celery Beat** | Runs periodic tasks: YouTube quota reset tracking at midnight PT, queue depth monitoring, daily analytics summary to Telegram. |
| Task Monitoring | **Flower** | Web UI for real-time Celery task monitoring. View running tasks, worker status, task history, and failure rates. |

---

## Database Layer

| Decision | Choice | Why |
|---|---|---|
| Primary Database | **PostgreSQL 16** | ACID compliance for job state machine. JSONB columns for flexible metadata storage (AI-generated metadata, copyright scan results). `gen_random_uuid()` for primary keys. |
| ORM | **SQLAlchemy 2.x (async mode)** | Async SQLAlchemy with asyncpg driver provides non-blocking database I/O. Critical for the async bot layer. Clean migration path from SQLite in development. |
| Async Driver | **asyncpg** | Fastest PostgreSQL driver for Python. Written in C extensions. Significantly faster than psycopg2 for connection-heavy async workloads. |
| Migrations | **Alembic** | SQLAlchemy's official migration tool. Version-controlled schema changes. Auto-generates migration scripts from model changes. |
| Development DB | **SQLite via SQLAlchemy** | Zero-config local development. Switch to PostgreSQL for production via single `DATABASE_URL` change. |
| Caching | **Redis (same instance)** | Quota usage counters, session state, and generated metadata caches all live in Redis. TTL-based expiration handles cache invalidation automatically. |

---

## Storage Layer

| Decision | Choice | Why |
|---|---|---|
| File Storage | **Cloudflare R2 (primary) / AWS S3 (fallback)** | R2 has zero egress fees — critical when serving video files multiple times during pipeline stages. S3-compatible API means the same `boto3` client works for both. |
| Local Temp | **`/tmp/kidstoon/[job_id]/`** | Each job gets its own isolated temp directory. Cleaned up after successful S3 upload. Prevents jobs from interfering with each other's files. |
| File Lifecycle | **S3 lifecycle policy: auto-delete after 48h** | Videos in the pipeline are temporary. Once uploaded to YouTube and verified, the S3 copy is no longer needed. Keeps storage costs near zero. |
| Access Pattern | **Pre-signed URLs (1h expiry)** | No public S3 bucket. Every access (Celery worker reads, thumbnail service reads) uses a time-limited pre-signed URL. Secure by default. |

---

## YouTube Integration Layer

| Decision | Choice | Why |
|---|---|---|
| Upload Method | **YouTube Data API v3, resumable protocol** | Only legitimate method. Resumable upload survives network interruptions and retries without wasting quota units. Simple upload fails permanently on network error. |
| Auth | **OAuth2 with refresh token** | Long-lived refresh token stored encrypted in environment. Access tokens auto-refreshed. No manual re-authentication needed. |
| Quota Management | **Custom QuotaManager class backed by Redis** | Tracks daily unit consumption. Refuses to start uploads within 2,000 units of the daily limit. Logs every API call's unit cost. Resets counter at midnight Pacific Time. |
| Upload Scheduling | **Celery Beat + `publishAt` field** | Videos are uploaded immediately but set to publish at optimal time (typically 2–4 PM local time for kids content). Allows uploading overnight at low-traffic times while scheduling public release for peak hours. |
| Metadata | **snippet + status + recordingDetails** | All fields populated: title, description, tags, category (25 = Education), language, made_for_kids, default_language. Fully formed metadata on first upload — no second API call needed. |
| Error Handling | **Quota exceeded → queue, 5xx → retry, 403 → alert** | Differentiates transient errors (retry) from permanent errors (alert admin) from quota limits (schedule for tomorrow). |

---

## Infrastructure & Deployment

| Decision | Choice | Why |
|---|---|---|
| Containerization | **Docker** | Reproducible environments. Each service (bot, workers, scheduler) runs in its own container. No "works on my machine" issues. |
| Orchestration (dev) | **Docker Compose** | One command starts all services: bot, 4 worker types, Redis, PostgreSQL, Flower, Prometheus, Grafana. |
| Orchestration (prod) | **Kubernetes** | Auto-scales worker pods based on queue depth. Self-heals crashed containers. Rolling deployments with zero downtime. |
| Cloud Provider | **DigitalOcean** (recommended) | Simpler than AWS for this scale. Managed Kubernetes (DOKS), managed PostgreSQL, Spaces (S3-compatible) all available. ~40% cheaper than equivalent AWS setup. |
| CI/CD | **GitHub Actions** | On push to main: run tests → build Docker image → push to registry → trigger Kubernetes rolling deployment. Full pipeline in under 5 minutes. |
| Secrets Management | **Kubernetes Secrets + Doppler** | Never store secrets in code or Docker images. Doppler syncs secrets to Kubernetes Secrets automatically. Rotation is a Doppler config change, not a code deployment. |

---

## Observability Stack

| Decision | Choice | Purpose |
|---|---|---|
| Error Tracking | **Sentry** | Captures exceptions with full stack trace, request context, and user info. Groups similar errors. Alerts on new error types. |
| Distributed Tracing | **OpenTelemetry + Jaeger** | Traces a single video job across bot handler → Celery tasks → FFmpeg → API calls as one unified timeline. Pinpoints exactly where slow pipelines lose time. |
| Metrics | **Prometheus + Grafana** | Custom metrics: pipeline stage durations, queue depths, quota remaining, generation success rates, cost per video. |
| Logging | **structlog** | Structured JSON logs with consistent fields: job_id, user_id, stage, duration_ms. Machine-parseable, searchable in any log aggregator. |
| Alerting | **Grafana Alerts → Telegram** | Alerts go directly to your admin Telegram chat. No email inbox to check. Actionable alerts only — quota warnings, failure rate spikes, dead letter queue growth. |

---

## Security Considerations

| Area | Approach |
|---|---|
| API Key Storage | Environment variables only. Never in code, logs, or Docker images. Rotated quarterly. |
| Database | Network-isolated. Only accessible from application containers. Strong password, SSL enforced. |
| S3/R2 | No public bucket. All access via pre-signed URLs with short expiry. |
| Telegram Access | Whitelist of authorized Telegram user IDs. All others silently ignored. |
| Input Validation | All user inputs (topics, style preferences) validated and sanitized via Pydantic before entering the pipeline. AI prompt injection is mitigated by sandboxing user input in clearly delimited sections of prompts. |
| COPPA | All uploads marked `madeForKids: true`. No user data collection. Compliance is structural, not optional. |

---

## Cost Model at Scale

| Component | Cost per Video | Cost at 5 Videos/Day | Notes |
|---|---|---|---|
| Claude (script + metadata) | $0.02 | $3/mo | 1,000 input tokens + 800 output tokens |
| DALL-E 3 (8 images) | $0.20 | $30/mo | $0.04 per 1024x1024 image |
| Runway ML (30 clips × 5s) | $0.50 | $75/mo | ~4 credits per 5-second clip |
| ElevenLabs (voiceover) | $0.10 | $15/mo | ~3 min of audio per video |
| Server (DigitalOcean) | $0.05 | $48/mo flat | 4 vCPU / 8GB Droplet |
| S3/R2 Storage | $0.01 | $1.50/mo | Lifecycle deletes after 48h |
| **Total** | **~$0.88** | **~$172/mo** | |

**Revenue potential:** Kids channel monetized at $2 CPM × 100k views/month = $200/month AdSense
This is conservative — established kids channels see $3–$8 CPM and millions of views.

---

*Last updated: 2026 | KidsToon AI v1.0*
