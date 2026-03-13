# ⚙️ PIPELINE.md — Complete Application Pipeline Reference
## KidsToon AI — Every Stage, Every Decision, Every Failure Mode

> This document is the technical bible for the KidsToon AI pipeline.  
> Every stage is documented with: what it does, how it does it, what can fail, and how failures are handled.

---

## Pipeline Overview

A single job moves through 8 stages. Each stage is a Celery task. Each task is atomic, idempotent, and independently retriable.

```
STAGE 1: INPUT VALIDATION & JOB CREATION
          │
          ▼
STAGE 2: SCRIPT & STRUCTURE GENERATION  [Queue: intelligence]
          │
          ▼
STAGE 3: IMAGE GENERATION PER SCENE     [Queue: generation]
          │
          ▼
STAGE 4: VIDEO CLIP GENERATION          [Queue: generation]
          │
          ▼
STAGE 5: VOICEOVER GENERATION           [Queue: generation]
          │
          ▼
STAGE 6: VIDEO ASSEMBLY                 [Queue: assembly]
          │
          ▼
STAGE 7: METADATA & THUMBNAIL           [Queue: intelligence]
          │
          ▼
STAGE 8: YOUTUBE UPLOAD & VERIFICATION  [Queue: upload]
```

---

## Stage 1: Input Validation & Job Creation

### Trigger
User sends `/generate` command in Telegram. Aiogram FSM captures the topic and configuration through a multi-step conversation.

### What Happens

```python
# FSM collects:
{
    "topic": "Counting Animals 1 to 10",
    "style": "cartoon",           # cartoon | watercolor | flat_design
    "duration_target": 180,       # seconds
    "language": "en",
    "publish_time": "14:00",      # 2PM local time
    "channel_id": "UCxxxx"
}
```

**Validation checks run synchronously in the bot handler (not queued):**
1. Topic length: 5–200 characters
2. Topic content: Claude API lightweight moderation check (100ms call)
3. User has no more than `MAX_CONCURRENT_JOBS` (default: 3) active jobs
4. YouTube quota check: does enough quota remain for an upload today or tomorrow?
5. Channel is authenticated and refresh token is valid

**If all checks pass:**
- Create `PipelineJob` record in PostgreSQL with `status = "queued"`
- Generate unique `job_id` (UUID4)
- Create isolated temp directory `/tmp/kidstoon/{job_id}/`
- Enqueue `generate_script` Celery task
- Send user: *"✅ Job queued! I'll update you as each stage completes."*

### Failure Handling
- Invalid topic → immediate bot message with reason, no job created
- Quota insufficient → bot offers to schedule for tomorrow
- Too many concurrent jobs → bot tells user how many are running and to wait

---

## Stage 2: Script & Structure Generation

**Queue:** `intelligence` | **Worker concurrency:** 6 | **Timeout:** 90 seconds

### What Happens

A single Claude API call generates the complete video structure as a JSON object.

```python
SYSTEM_PROMPT = """
You are a children's educational content writer specializing in YouTube videos for ages 2-6.
You create warm, engaging, repetitive scripts that help children learn through fun characters.

Rules:
- Language must be simple, clear, and appropriate for toddlers
- Every script must have a clear learning objective
- Characters must be friendly, colorful animals or creatures
- Repetition is educational — repeat key concepts 2-3 times
- End with a recap and encouragement
- No scary elements, conflict, or complex emotions
- Maximum sentence length: 10 words

Output ONLY valid JSON matching the provided schema. No preamble.
"""

OUTPUT_SCHEMA = {
    "title": "string (max 60 chars)",
    "learning_objective": "string",
    "character": {
        "name": "string",
        "species": "string",
        "appearance": "detailed string for image generation"
    },
    "scenes": [
        {
            "scene_number": "int",
            "duration_seconds": "int (4-6)",
            "narration": "string (what the voiceover says)",
            "visual_description": "string (what the image should show)",
            "image_prompt": "string (DALL-E optimized prompt)"
        }
    ],
    "background_music_mood": "string (e.g., 'cheerful, upbeat, gentle')",
    "tags": ["array of 25 YouTube tags"],
    "description": "string (SEO-optimized, 500 words)",
    "chapters": [{"time": "0:00", "title": "string"}]
}
```

**Scene count calculation:**
```python
num_scenes = duration_target // 5  # 180 seconds → 36 scenes
```

**Character prompt engineering for consistency:**
Every `image_prompt` in every scene includes the full character description from `character.appearance`. This is the primary mechanism for visual consistency before LoRA fine-tuning is available.

```
Example character appearance string:
"Benny the Bear: a small, chubby brown bear cub with round ears, bright blue eyes, 
a cream-colored belly, wearing a red polka-dot bow tie. Cute, friendly, cartoon style. 
Pixar-like 3D rendering. Soft lighting."
```

### Persistence
- Full script JSON saved to PostgreSQL `pipeline_jobs.script_data` (JSONB column)
- Also saved to `/tmp/kidstoon/{job_id}/script.json`
- Update `status = "script_generated"`

### Failure Modes & Handling
| Failure | Cause | Handling |
|---|---|---|
| Invalid JSON response | Claude API deviation | Retry with stricter prompt. Max 2 retries. |
| Schema validation error | Missing required field | Re-request only the missing field |
| API timeout (>90s) | Claude overloaded | Retry with exponential backoff |
| Moderation refusal | Inappropriate topic slipped through | Mark job failed, notify user with reason |
| API rate limit | Too many concurrent calls | Retry after 60 seconds |

---

## Stage 3: Image Generation Per Scene

**Queue:** `generation` | **Worker concurrency:** 3 | **Timeout:** 30 min (for full scene set)

### What Happens

For each scene in the script, generate one image using DALL-E 3. Scenes are processed in batches of 5 to respect rate limits (50 images/min on Tier 1).

```python
async def generate_scene_image(scene: SceneData, character: CharacterData) -> str:
    # Construct the full prompt with character description injected
    full_prompt = f"""
    {scene.image_prompt}
    
    The main character: {character.appearance}
    
    Style: Children's cartoon illustration, bright colors, simple shapes, 
    friendly and warm atmosphere, white background or simple colorful background.
    No text in the image. Safe for children. High quality.
    """
    
    response = await openai_client.images.generate(
        model="dall-e-3",
        prompt=full_prompt,
        size="1792x1024",  # Cinematic 16:9 for video
        quality="standard",  # "hd" for thumbnails only — 2x cost not justified per frame
        n=1
    )
    
    # Download and save immediately — DALL-E URLs expire in 1 hour
    image_path = f"/tmp/kidstoon/{job_id}/frames/scene_{scene.scene_number:03d}.png"
    await download_and_save(response.data[0].url, image_path)
    
    return image_path
```

**Rate limiting implementation:**
```python
# Token bucket: 50 requests per minute, burst of 5
@rate_limit(requests_per_minute=45, burst=5)  # 10% safety margin
async def generate_scene_image(scene, character):
    ...
```

**Batch processing with progress updates:**
Every 5 scenes, update the PostgreSQL job record and send a Telegram progress message:
*"🎨 Generating images... 15/36 scenes complete"*

### Consistency Enforcement
After every 10 scenes, run a CLIP similarity check:
```python
from transformers import CLIPProcessor, CLIPModel

def check_character_consistency(image_paths: list[str], reference_path: str) -> float:
    """Returns average cosine similarity to reference character image. 
    Threshold: 0.75. Below threshold → regenerate with stronger character prompt."""
    ...
```

If any image scores below 0.70 similarity to the reference character image, it is automatically regenerated with a reinforced character description prompt.

### Storage
- Images saved to local temp during generation
- Batch-uploaded to S3 `/{job_id}/frames/` after all scenes complete
- Pre-signed URLs generated for video generation stage

### Failure Modes & Handling
| Failure | Cause | Handling |
|---|---|---|
| Content policy refusal | Prompt contains edge-case content | Regenerate with sanitized prompt (remove adjectives, simplify) |
| Rate limit 429 | Burst exceeded | Wait 60s, retry |
| URL expired before download | Slow network | Regenerate (fast, idempotent) |
| CLIP similarity fail | Character looks wrong | Regenerate scene with `[CHARACTER CONSISTENCY: CRITICAL]` prefix |
| Runway API down | Service outage | Switch to Pika Labs fallback automatically |

---

## Stage 4: Video Clip Generation

**Queue:** `generation` | **Worker concurrency:** 3 | **Timeout:** 45 min

### What Happens

For each scene image, generate a 5-second video clip showing gentle motion (camera pan, character breathing, background elements moving).

```python
async def generate_video_clip(image_path: str, scene: SceneData) -> str:
    # Upload image to Runway ML (requires URL, not local path)
    image_url = await s3_client.get_presigned_url(f"{job_id}/frames/{scene.scene_number:03d}.png")
    
    # Motion prompt — gentle motion appropriate for kids
    motion_prompt = f"""
    Gentle animation: subtle breathing motion, soft camera zoom in 5%, 
    background elements have slight movement. Character {scene.character_name} 
    is {scene.character_action}. Warm, friendly atmosphere. No sudden movements.
    """
    
    task = await runway_client.image_to_video.create(
        model="gen3a_turbo",
        prompt_image=image_url,
        prompt_text=motion_prompt,
        duration=5,  # seconds
        ratio="1280:720"
    )
    
    # Poll for completion (Runway is async)
    clip_url = await poll_until_complete(task.id, timeout=300)
    
    # Download
    clip_path = f"/tmp/kidstoon/{job_id}/clips/scene_{scene.scene_number:03d}.mp4"
    await download_and_save(clip_url, clip_path)
    
    return clip_path
```

**Parallelization strategy:**
Runway ML allows concurrent jobs. Run up to 3 simultaneous video generation requests per worker. With 3 workers × 3 concurrent = 9 simultaneous Runway jobs. 36 scenes ÷ 9 = ~4 batches. Each clip takes ~60–90 seconds → total clip generation time: ~6 minutes.

**Integrity verification after download:**
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=duration,codec_name \
  -of json clip_scene_001.mp4
# Expected: duration ≈ 5.0, codec_name = "h264"
```
Any clip failing integrity check is regenerated before moving to assembly.

### Failure Modes & Handling
| Failure | Cause | Handling |
|---|---|---|
| Runway timeout >5min | Complex scene | Retry with simpler motion prompt |
| Runway rate limit | Credit exhaustion | Switch to Pika Labs fallback |
| Corrupted clip | Network issue | Delete and regenerate |
| Wrong duration | API inconsistency | FFmpeg trim to exactly 5s |

---

## Stage 5: Voiceover Generation

**Queue:** `generation` | **Worker concurrency:** 6 | **Timeout:** 10 min

### What Happens

Generate one audio file per scene containing the scene's narration text.

```python
async def generate_voiceover(scene: SceneData) -> str:
    # Add SSML-like pacing markers for natural delivery
    text_with_pacing = add_pacing_marks(scene.narration)
    # e.g., "One elephant! <break time='0.5s'/> Can you count with me?"
    
    audio = await elevenlabs_client.generate(
        text=text_with_pacing,
        voice=VOICE_ID,  # Pre-selected warm, clear kids narrator voice
        model="eleven_turbo_v2_5",
        voice_settings=VoiceSettings(
            stability=0.55,         # Some variation for naturalness
            similarity_boost=0.75,  # High fidelity to voice character
            style=0.30,             # Moderate expressiveness
            use_speaker_boost=True
        )
    )
    
    audio_path = f"/tmp/kidstoon/{job_id}/audio/scene_{scene.scene_number:03d}.mp3"
    with open(audio_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    
    return audio_path
```

**Silence trimming:**
After generation, trim leading/trailing silence with FFmpeg:
```bash
ffmpeg -i scene_001.mp3 -af silenceremove=start_periods=1:start_silence=0.1:stop_periods=1:stop_silence=0.1 scene_001_trimmed.mp3
```

**Duration alignment:**
Calculate actual audio duration. If voiceover is longer than the 5-second clip, the clip will be extended by repeating its last frame using FFmpeg `tpad` filter. If shorter, silence is padded.

### Music Selection
Run in parallel with voiceover generation:

```python
async def select_background_music(mood: str, duration: int) -> str:
    # Query Freesound API with mood keywords
    tracks = await freesound_client.search(
        query=f"children background music {mood}",
        filter="license:Attribution OR license:CreativeCommons0",
        sort="rating_desc",
        page_size=10
    )
    
    # Select track longer than video duration
    suitable = [t for t in tracks if t.duration >= duration]
    selected = suitable[0]  # Highest rated
    
    return await download_track(selected.id)
```

### Failure Modes & Handling
| Failure | Cause | Handling |
|---|---|---|
| ElevenLabs API error | Service issue | Retry 3x, then fallback to Google TTS |
| Character limit exceeded | Long narration text | Split into two calls, concatenate |
| Audio too long | ElevenLabs speaks slowly | Speed up 5% with FFmpeg atempo filter |
| No suitable music found | Freesound API timeout | Use pre-bundled fallback track library |

---

## Stage 6: Video Assembly

**Queue:** `assembly` | **Worker concurrency:** 2 | **Timeout:** 30 min

### What Happens

This is the most computationally intensive stage. FFmpeg assembles everything into the final video in a single-pass filter graph where possible.

#### Sub-Stage 6.1: Per-Scene Assembly

For each scene, combine the video clip with its voiceover. Extend clip duration if voiceover is longer:

```python
def assemble_scene(clip_path, audio_path, scene_duration) -> str:
    output_path = clip_path.replace('.mp4', '_with_audio.mp4')
    
    (
        ffmpeg
        .input(clip_path)
        .input(audio_path)
        .output(
            output_path,
            vcodec='libx264',
            acodec='aac',
            preset='fast',
            t=scene_duration,  # Trim or pad to exact duration
            shortest=None      # Use video duration, not audio
        )
        .overwrite_output()
        .run(quiet=True)
    )
    return output_path
```

#### Sub-Stage 6.2: Scene Concatenation

Concatenate all scene clips with smooth crossfade transitions:

```python
def concatenate_scenes_with_transitions(scene_clips: list[str]) -> str:
    # Build xfade filter chain
    # Each transition: 0.3 second crossfade
    inputs = [ffmpeg.input(clip) for clip in scene_clips]
    
    # Chain xfade filters
    video = inputs[0].video
    audio = inputs[0].audio
    
    for i, (next_input) in enumerate(inputs[1:], 1):
        offset = sum(get_duration(c) for c in scene_clips[:i]) - 0.3
        video = ffmpeg.filter([video, next_input.video], 'xfade',
                             transition='fade', duration=0.3, offset=offset)
        audio = ffmpeg.filter([audio, next_input.audio], 'acrossfade',
                             d=0.3)
    
    return video, audio
```

#### Sub-Stage 6.3: Audio Mix

Mix voiceover (assembled in scenes) with background music:

```python
def mix_audio(assembled_video, music_path, total_duration) -> str:
    music = ffmpeg.input(music_path)
    
    # Loop music if shorter than video
    music_looped = music.audio.filter('aloop', loop=-1, size=2e+09)
    
    # Trim music to video length
    music_trimmed = music_looped.filter('atrim', duration=total_duration)
    
    # Reduce music volume to -18dB relative (voice is primary)
    music_quiet = music_trimmed.filter('volume', volume=0.15)
    
    # Mix: voice + music
    mixed_audio = ffmpeg.filter(
        [assembled_video.audio, music_quiet],
        'amix', inputs=2, duration='first'
    )
    
    # Apply EBU R128 loudness normalization (two-pass)
    normalized = mixed_audio.filter('loudnorm', I=-16, TP=-1.5, LRA=11)
    
    return mixed_audio
```

#### Sub-Stage 6.4: Subtitle Burning

Generate ASS subtitle file from scene narrations and burn into video:

```python
def generate_ass_subtitles(scenes: list[SceneData], output_path: str):
    ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,Bold,Outline,Shadow,Alignment
Style: Kids,Arial Rounded MT Bold,52,&H00FFFFFF,1,3,1,2

[Events]
Format: Layer,Start,End,Style,Text
"""
    for scene in scenes:
        start = format_ass_time(scene.start_time)
        end = format_ass_time(scene.start_time + scene.duration)
        text = scene.narration.replace('\n', '\\N')
        ass_content += f"Dialogue: 0,{start},{end},Kids,,{text}\n"
    
    with open(output_path, 'w') as f:
        f.write(ass_content)

# Burn subtitles in FFmpeg:
# .filter('ass', subtitle_path)
```

**Subtitle style for kids content:**
- Font: Arial Rounded MT Bold (clean, friendly)
- Size: 52pt (large, readable on phone screens)
- Color: White with 3px black outline
- Position: Bottom center (Alignment: 2)
- One line maximum per subtitle entry

#### Sub-Stage 6.5: Final Render

Single FFmpeg command combining all stages that couldn't be chained:

```bash
ffmpeg \
  -i assembled_with_audio.mp4 \
  -vf "ass=subtitles.ass,
       drawtext=fontfile=/fonts/logo.ttf:text='KidsToon':
                fontcolor=white:fontsize=24:
                x=w-tw-20:y=20:
                box=1:boxcolor=black@0.3:boxborderw=5" \
  -c:v h264_nvenc \    # GPU if available, else libx264
  -preset fast \
  -crf 23 \
  -c:a aac \
  -b:a 192k \
  -movflags +faststart \  # Enable streaming — required for YouTube
  -y final_output.mp4
```

`-movflags +faststart` moves the MOOV atom to the beginning of the file, enabling YouTube to start processing the video before it's fully uploaded.

### Output Verification

After render, verify the output file:
```python
def verify_output(path: str) -> VideoMetrics:
    probe = ffmpeg.probe(path)
    video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    audio_stream = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
    
    assert video_stream['codec_name'] == 'h264'
    assert audio_stream['codec_name'] == 'aac'
    assert float(probe['format']['duration']) > 30  # At least 30 seconds
    assert int(probe['format']['size']) < 2_000_000_000  # Under 2GB
    
    return VideoMetrics(
        duration=float(probe['format']['duration']),
        size_bytes=int(probe['format']['size']),
        width=int(video_stream['width']),
        height=int(video_stream['height'])
    )
```

### Failure Modes & Handling
| Failure | Cause | Handling |
|---|---|---|
| FFmpeg OOM killed | Video too long / 4K input | Reduce concurrent renders, downscale input |
| Subtitle encoding error | Special characters in narration | Sanitize narration text before ASS generation |
| Duration mismatch | Scene timing calculation error | Re-calculate with actual measured durations |
| Output file corrupt | Disk full / hardware error | Clean temp dir, re-run assembly |
| GPU not available | NVENC driver issue | Auto-fallback to libx264 |

---

## Stage 7: Metadata & Thumbnail Generation

**Queue:** `intelligence` | **Worker concurrency:** 6 | **Timeout:** 5 min

### Thumbnail Generation

```python
def create_thumbnail(video_path: str, script: ScriptData) -> str:
    # Step 1: Extract best frame using scene detection
    scenes = detect_scenes(video_path)  # PySceneDetect
    best_frame_time = select_most_engaging_frame(scenes)  # CLIP scoring
    
    # Step 2: Extract frame
    frame_path = f"/tmp/kidstoon/{job_id}/thumbnail_base.jpg"
    ffmpeg.input(video_path, ss=best_frame_time).output(
        frame_path, vframes=1, q=2
    ).run()
    
    # Step 3: Compose thumbnail with Pillow
    img = Image.open(frame_path).resize((1280, 720))
    
    # Add colored gradient overlay at bottom
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([0, 500, 1280, 720], fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img.convert('RGBA'), overlay)
    
    # Add bold title text
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype('/fonts/Fredoka-Bold.ttf', 72)
    draw.text((640, 600), script.title, font=font, fill='white',
              stroke_width=3, stroke_fill='black', anchor='ms')
    
    # Add channel logo watermark (top-right)
    logo = Image.open('/assets/channel_logo.png').resize((80, 80))
    img.paste(logo, (1180, 20), mask=logo)
    
    thumbnail_path = f"/tmp/kidstoon/{job_id}/thumbnail.jpg"
    img.convert('RGB').save(thumbnail_path, 'JPEG', quality=95)
    
    return thumbnail_path
```

**Thumbnail spec:** 1280×720px, JPEG, under 2MB (YouTube requirement)

### Final Metadata Validation

The metadata was generated in Stage 2 alongside the script. In Stage 7, it's validated and enhanced:

```python
def validate_and_enhance_metadata(metadata: VideoMetadata, actual_duration: float) -> VideoMetadata:
    # Update chapter timestamps based on actual video duration
    # (Script estimated 5s/scene, reality may differ slightly)
    metadata.chapters = recalculate_chapters(metadata.chapters, actual_duration)
    
    # Add standard end-of-description footer
    metadata.description += "\n\n" + STANDARD_FOOTER  
    # STANDARD_FOOTER contains: channel links, playlist link, parent resources
    
    # Validate tag count (YouTube max: 500 chars total across all tags)
    metadata.tags = optimize_tags(metadata.tags)  # Trim to fit 500 char limit
    
    return metadata
```

---

## Stage 8: YouTube Upload & Verification

**Queue:** `upload` | **Worker concurrency:** 4 | **Timeout:** 60 min

### Quota Pre-Check

```python
async def pre_upload_quota_check() -> bool:
    quota_manager = QuotaManager()
    remaining = await quota_manager.get_remaining_quota()
    
    if remaining < 2000:  # Safety buffer
        # Schedule for tomorrow after quota reset
        eta = get_next_quota_reset()  # Midnight Pacific Time
        raise QuotaExhaustedError(f"Upload scheduled for {eta}")
    
    return True
```

### Upload Execution

```python
async def upload_to_youtube(
    video_path: str,
    thumbnail_path: str,
    metadata: VideoMetadata,
    channel_credentials: OAuth2Credentials
) -> str:
    
    youtube = build('youtube', 'v3', credentials=channel_credentials)
    
    body = {
        "snippet": {
            "title": metadata.title,
            "description": metadata.description,
            "tags": metadata.tags,
            "categoryId": "25",            # "Education" category
            "defaultLanguage": metadata.language,
            "defaultAudioLanguage": metadata.language,
        },
        "status": {
            "privacyStatus": "private",    # Private until scheduled publish time
            "publishAt": metadata.publish_at.isoformat(),
            "madeForKids": True,           # COPPA compliance — mandatory
            "selfDeclaredMadeForKids": True
        },
        "recordingDetails": {
            "recordingDate": datetime.now().isoformat()
        }
    }
    
    # Resumable upload — survives network interruptions
    media = MediaFileUpload(
        video_path,
        chunksize=10 * 1024 * 1024,  # 10MB chunks
        resumable=True,
        mimetype="video/mp4"
    )
    
    insert_request = youtube.videos().insert(
        part="snippet,status,recordingDetails",
        body=body,
        media_body=media
    )
    
    # Track quota usage
    await quota_manager.consume(1600)  # Video insert = 1600 units
    
    # Execute upload with progress tracking
    video_id = None
    response = None
    
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            await update_job_progress(f"⬆️ Uploading to YouTube... {progress}%")
    
    video_id = response['id']
    
    # Upload thumbnail (separate API call: 50 quota units)
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
    ).execute()
    await quota_manager.consume(50)
    
    # Add to playlist if series
    if metadata.playlist_id:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": metadata.playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id}
                }
            }
        ).execute()
        await quota_manager.consume(50)
    
    return f"https://youtube.com/watch?v={video_id}"
```

### Post-Upload Verification

```python
async def verify_upload(video_id: str, youtube_client) -> bool:
    # Wait up to 5 minutes for YouTube to acknowledge the upload
    for attempt in range(10):
        video = youtube_client.videos().list(
            part="status,processingDetails",
            id=video_id
        ).execute()
        
        if not video['items']:
            await asyncio.sleep(30)
            continue
        
        status = video['items'][0]['status']['uploadStatus']
        
        if status == 'uploaded':
            return True
        elif status == 'failed':
            raise YouTubeUploadError(f"YouTube processing failed: {video['items'][0]}")
        
        await asyncio.sleep(30)
    
    return False  # Timeout — but video may still be processing
```

### Cleanup

```python
async def cleanup_job_files(job_id: str):
    # Delete local temp directory
    shutil.rmtree(f"/tmp/kidstoon/{job_id}", ignore_errors=True)
    
    # Delete S3 files (or set to expire — lifecycle policy handles this)
    await s3_client.delete_prefix(f"{job_id}/")
    
    # Update job record
    await db.update_job(job_id, {
        "status": "completed",
        "completed_at": datetime.now(),
        "youtube_url": youtube_url
    })
```

### User Notification

```python
await bot.send_message(
    chat_id=user.telegram_id,
    text=f"""
🎉 *Video Published Successfully!*

📺 *{metadata.title}*
⏱ Duration: {format_duration(actual_duration)}
📅 Scheduled: {metadata.publish_at.strftime('%B %d at %I:%M %p')}
🔗 {youtube_url}

_Total processing time: {total_duration_minutes} minutes_
""",
    parse_mode="Markdown"
)
```

---

## Cross-Cutting Concerns

### Idempotency

Every Celery task checks if it has already completed before running:

```python
@celery.task(bind=True)
def generate_scene_image(self, job_id: str, scene_number: int):
    # Check if this specific output already exists
    output_path = f"/tmp/kidstoon/{job_id}/frames/scene_{scene_number:03d}.png"
    
    if os.path.exists(output_path) and is_valid_image(output_path):
        logger.info(f"Scene {scene_number} already generated, skipping")
        return output_path  # Idempotent — return existing result
    
    # ... rest of generation logic
```

This means if a task is accidentally run twice (network blip caused false failure), the second run is a no-op. Critical for preventing duplicate YouTube uploads.

### Job State Machine

```
queued → script_generated → images_generating → images_complete 
       → clips_generating → clips_complete 
       → voiceover_generating → voiceover_complete
       → assembling → assembled
       → uploading → completed
       
Any stage → failed → (manual retry → back to previous state)
Any stage → failed (max retries) → dead_letter
```

State transitions are atomic (PostgreSQL transactions). No job can be in two states simultaneously.

### Observability Per Stage

Every stage emits:
1. **OpenTelemetry span** — with stage name, job_id, and timing
2. **Prometheus counter** — `pipeline_stage_complete_total{stage="image_generation"}`
3. **Prometheus histogram** — `pipeline_stage_duration_seconds{stage="image_generation"}`
4. **Structured log entry** — JSON with all relevant context

This means for any completed video, you can trace exactly how long every stage took and calculate the cost breakdown per stage.

### Cost Tracking Per Job

```python
# Logged after each API call:
cost_tracker.log_api_call(
    job_id=job_id,
    service="openai_dalle3",
    units=1,
    cost_usd=0.040,
    scene_number=scene_number
)

# Aggregated in the completion notification:
# "Total generation cost: $0.94"
```

---

## Pipeline Performance Benchmarks

On a 4 vCPU / 8GB RAM server (no GPU):

| Stage | Duration (36-scene video) | Bottleneck |
|---|---|---|
| Stage 1: Validation | <1 second | — |
| Stage 2: Script Generation | 8–15 seconds | Claude API |
| Stage 3: Image Generation | 8–12 minutes | DALL-E 3 rate limits |
| Stage 4: Video Clip Generation | 5–8 minutes | Runway ML (parallel) |
| Stage 5: Voiceover | 3–5 minutes | ElevenLabs API |
| Stage 6: Assembly | 4–7 minutes | CPU (FFmpeg) |
| Stage 7: Metadata + Thumbnail | 30–60 seconds | CLIP scoring |
| Stage 8: Upload | 2–8 minutes | Network bandwidth |
| **Total** | **~25–45 minutes** | |

**With GPU node for Stage 6:**
Assembly drops from 7 minutes to ~90 seconds.
Total pipeline: ~18–30 minutes per video.

---

## Environment-Specific Configurations

### Development
- Use SQLite instead of PostgreSQL
- Use local filesystem instead of S3
- Use `dall-e-2` instead of `dall-e-3` (10x cheaper for testing)
- Set `UPLOAD_TO_YOUTUBE=false` — save final video locally instead
- Use `MOCK_RUNWAY=true` — return a pre-recorded test clip instead of calling Runway API

### Staging
- Full stack, real APIs
- Upload to a private unlisted YouTube channel
- Set `MAX_CONCURRENT_JOBS=1` — slow but validates the full pipeline

### Production
- Full stack, optimized concurrency
- Upload to production channel with scheduled publish
- All observability enabled
- Auto-scaling on Kubernetes

---

*KidsToon AI Pipeline Documentation | v1.0 | Generated 2026*
