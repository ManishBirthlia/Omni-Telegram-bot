# 📋 Omni Telegram Bot — Project Memo

**Date:** March 27, 2026
**Commits recent:** 11 | **Files changed:** 15 | **Lines added:** ~1200

---

## ✅ Recent Completed Work (March 26-27)

### 1. Local AI Migration & GPU Acceleration *(MAJOR)*
- Migrated **Whisper** (Transcription) and **Bark** (Audio Generation) to run locally on **NVIDIA GTX 1660 Ti**.
- Enabled **CUDA** support for both models, significantly improving performance and removing the "FP16 not supported on CPU" warnings.
- Fixed PyTorch 2.6 security restrictions by monkey-patching `torch.load` for legacy model files.

### 2. Enhanced Audio Generation (Suno Bark)
- **Smart Chunking**: Implemented automatic text splitting (~150 chars) and audio merging (`numpy.concatenate`) to bypass Bark's 14-second limit.
- **Audio-to-Audio**: Integrated transcription into the audio generation flow — users can now send voice notes to be "re-spoken" by AI.
- **Non-speech Tags**: Added support and documentation for tags like `[laughs]`, `[clears throat]`, etc.

### 3. Transcription Fixes
- Resolved `Transcription error: expected np.ndarray (got _io.BufferedReader)` bug by passing file paths and using `asyncio.to_thread`.
- Verified end-to-end local transcription working on GPU.

---

## ✅ Previously Completed Work (March 19)

### 1. Unified Downloader & Merged Command *(UPDATE)*
- Merged YouTube and Instagram downloaders into a single `/downloader` command.
- Automatically handles any supported video link (YouTube, Instagram, Twitter/X, TikTok, etc.).

### 2. Advanced AI Chat (Groq & NVIDIA)
- Updated `/chat` to use state-of-the-art models:
  - **Groq**: `llama-3.3-70b-versatile`
  - **NVIDIA**: `nvidia/nemotron-3-nano-30b-a3b`

### 2. Video Generation
- Integrated actual API call logic into `generateVideo.py` using the LTX Video API.

### 3. Polish
- Implemented `/help` command displaying all available commands.

---

## ✅ Previously Completed Work (March 17-18)

### 1. Image Generation Feature *(NEW)*
- Built `/imagine` command with **NVIDIA Picasso API** integration
- FSM flow: user sends prompt → bot generates image → delivers as photo
- Auto-cleanup of generated files after delivery
- Handles timeouts, API errors, and content-filter rejections gracefully

### 2. NVIDIA AI Chat Integration *(NEW)*
- Replaced Groq with **NVIDIA Nemotron 30B** as the `/chat` backend
- Streaming response accumulation (no more per-chunk message spam)
- Built [markdown_to_telegram_html()](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/bot/handlers/chat.py#6-70) converter — model Markdown renders as **bold**, *italic*, [code](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/bot/handlers/chat.py#21-27), ```code blocks```, • bullet lists, and blockquotes in Telegram
- Fallback: if HTML parsing fails, sends as plain text (never crashes)

### 3. Docker & Kubernetes Overhaul
- **Dockerfile** → Python 3.14, `uv sync`, multi-stage build, health check
- **docker-compose.yml** → health checks, proper DB name, volume mounts
- **docker-compose.prod.yml** → resource limits, named volumes, security hardening
- **k8s/deployment.yaml** → full stack (Bot, Celery, Redis, Postgres, PVCs, probes)
- Renamed everything from `kids-toon` → `omni-telegram-bot`

### 4. Bug Fixes & Cleanup
- Fixed [celery_app.py](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/workers/celery_app.py) app name (`kids_toons` → `omni_telegram_bot`)
- Fixed [pyproject.toml](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/pyproject.toml) name (spaces → underscores)
- Enabled file cleanup in [directDownloader.py](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/bot/handlers/directDownloader.py) and [generateImage.py](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/bot/handlers/generateImage.py)
- Fixed "message text is empty" Telegram errors from streaming
- Fixed `<br>` / `<think>` tag parse errors in chat responses

---

## 📌 Tomorrow's Tasks

### Priority 1 — Core Features
- [x] **Instagram Downloader** — replaced by unified `videoDownloader.py`
- [ ] **Transcription handler** — verify [transcribe.py](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/bot/handlers/transcribe.py) is working end-to-end
- [x] **Video Generation** — integrated real LTX-api calls in [generateVideo.py](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/bot/handlers/generateVideo.py)

### Priority 2 — Robustness
- [ ] **Conversation memory** for `/chat` — maintain chat history per user session instead of single-turn
- [ ] **Rate limiting** — prevent API abuse (e.g. max 5 image generations per user/hour)
- [ ] **Error reporting** — log errors to a file or channel instead of just `print()`

### Priority 3 — DevOps
- [ ] **[.env.example](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/.env.example)** — update template and remove outdated keys (contains legacy `kidstoon` variables)
- [ ] **Test the Docker setup** — `docker compose up` and verify all services start
- [ ] **CI/CD pipeline** — GitHub Actions for lint + build on push

### Priority 4 — Polish
- [x] **`/help` command** — implemented
- [ ] **Typing indicator** — show "typing…" while waiting for AI responses
- [ ] **README update** — add screenshots, setup instructions, and architecture diagram
