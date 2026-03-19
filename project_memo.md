# 📋 Omni Telegram Bot — Project Memo

**Date:** March 17–18, 2026 (Monday night session)
**Commits today:** 5 | **Files changed:** 16 | **Lines added:** ~1,169

---

## ✅ Today's Completed Work

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
- [ ] **Instagram Downloader** — finish [instaDownloader.py](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/bot/handlers/instaDownloader.py) (currently empty/stub)
- [ ] **Transcription handler** — verify [transcribe.py](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/bot/handlers/transcribe.py) is working end-to-end
- [ ] **Video Generation** — test [generateVideo.py](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/bot/handlers/generateVideo.py) flow with real API calls

### Priority 2 — Robustness
- [ ] **Conversation memory** for `/chat` — maintain chat history per user session instead of single-turn
- [ ] **Rate limiting** — prevent API abuse (e.g. max 5 image generations per user/hour)
- [ ] **Error reporting** — log errors to a file or channel instead of just `print()`

### Priority 3 — DevOps
- [ ] **[.env.example](file:///d:/My%20Business/My%20Projects/On-Going/Omni%20Telegram%20Bot/.env.example)** — create a template so new devs know which keys are needed
- [ ] **Test the Docker setup** — `docker compose up` and verify all services start
- [ ] **CI/CD pipeline** — GitHub Actions for lint + build on push

### Priority 4 — Polish
- [ ] **`/help` command** — list all available commands with descriptions
- [ ] **Typing indicator** — show "typing…" while waiting for AI responses
- [ ] **README update** — add screenshots, setup instructions, and architecture diagram
