import os
import re
import asyncio
import yt_dlp
import requests
import whisper
from openai import OpenAI
from pathlib import Path
from aiogram.types import FSInputFile
from aiogram import Bot, Dispatcher, types as aiogram_types, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from groq import Groq
from handlers.chat import groq_AI_chatting, nvidia_AI_chatting, deepseek_AI_chatting
from utilities import cancel_if_command, upload_to_gofile_async
from handlers.videoDownloader import (
    validate_video_url,
    download_video,
    fetch_formats,
    build_quality_keyboard,
    _fetch_and_show_qualities,
)
from handlers.generateVideo import start_video_generation
from handlers.generateAudio import start_audio_generation
from handlers.generateImage import (
    generate_image,
    build_aspect_ratio_keyboard,
    build_img_quality_keyboard,
    build_neg_prompt_keyboard,
)
from handlers.directDownloader import cmd_direct_download
from handlers.transcribe import process_transcription, transcribe_audio

# ── URL pattern — matches any http(s) link ─────────────────────
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
nvidia_chat_client_1 = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = os.getenv("NVIDIA_SIMPLE_CHAT_API_KEY")
) 
nvidia_chat_client_2 = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = os.getenv("NVIDIA_COMPLEX_CHAT_API_KEY")
)
import torch
device = "cuda" if torch.cuda.is_available() else "cpu"
whisper_client = whisper.load_model("small", device=device)
# openai_client = OpenAI()

#  FSM STATE GROUP
class BotStates(StatesGroup):
    chatting                 = State()   # /chat flow
    dl_waiting_for_url       = State()   # /downloader — step 1
    dl_waiting_for_quality   = State()   # /downloader — step 2
    Video_prompt             = State()   # /generateVideo — step 1
    Audio_prompt             = State()   # /generateVideo — step 2
    Image_prompt             = State()   # /generateImage — step 1: prompt
    Image_aspect_ratio       = State()   # /generateImage — step 2: aspect ratio
    Image_quality            = State()   # /generateImage — step 3: quality
    Image_negative           = State()   # /generateImage — step 4: negative prompt
    transcribe_waiting       = State()   # /transcribe — waiting for audio

#  BOT & DISPATCHER
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp  = Dispatcher(storage=MemoryStorage())

#  CONSTANTS
LTX_API_URL        = "https://api.ltx.video/v1/text-to-video"
DOWNLOAD_DIR       = Path("Youtube Downloads")
STORAGE_DIR        = Path("S3 Storage")
DOWNLOAD_DIR.mkdir(exist_ok=True)
STORAGE_DIR.mkdir(exist_ok=True)

TELEGRAM_MAX_BYTES = 50 * 1024 * 1024   # 50 MB — Telegram hard bot limit
WARN_SIZE_BYTES    = 45 * 1024 * 1024   # 45 MB — show ⚠️ warning on keyboard
DEFAULT_VID_TOPIC  = "A child sleeping and dreaming of counting sheep up to 10"


SYSTEM_INSTRUCTION = """
You are an AI assistant for Omni AI, a multi-purpose Telegram bot designed to be a personal Swiss Army knife. Instead of switching between 10 apps or websites, you message one bot and get things done:

- 📥 Paste a video link (YouTube, Instagram, Twitter/X, TikTok, …) → get the video downloaded
- 🎬 Describe a scene → get an AI-generated video
- 💬 Ask a question → get an AI-powered answer (Groq/LLaMA/Nvidia)
- 🎙️ Send audio → get a full transcription
- 📝 Generate Audio from Text
- 📸 Generate Image from Text
- 📹 Generate Video from Text

The vision: One bot that keeps getting smarter. Every useful tool you wish existed — built into one Telegram interface.

Available bot commands the user can use:
/start — Initialize the bot and authenticate
/chat — General chat with the AI assistant
/downloader — Download a video from YouTube, Instagram, Twitter/X, TikTok, and 1000+ sites
/generateAudio — Generate a single audio clip based on a prompt
/generateImage — Generate a single image based on a prompt
/generateVideo — Start a new single video generation
/transcribe — Transcribe audio or video link to text
/status — Check status of all running jobs
/queue — View pending job queue
/ytQuota — Check today's remaining YouTube API quota
/schedule — View and manage scheduled uploads
/platforms — View and manage connected social platforms
/models — View available AI models for each step
/cancel [job_id] — Cancel a running or queued job
/history — View last 10 completed jobs with video links
/settings — Configure default preferences
/help — Show all commands

Your job is to help the user with anything related to this project.
Always be helpful, friendly, and keep responses focused and actionable.
"""

HELP_TEXT = """
🤖 <b>Bot Commands</b>
/start — Initialize the bot and authenticate
/chat — General chat with the AI assistant
/downloader — Download video (YouTube, Instagram, Twitter/X, TikTok, …)
/generateImage — Generate a single image from a prompt
/generateAudio — Generate a single audio clip from a prompt
/generateVideo — Start a new single video generation
/transcribe — Transcribe audio or a video link to text
/status — Check status of all running jobs
/queue — View pending job queue
/ytQuota — Check today's remaining YouTube API quota
/schedule — View and manage scheduled uploads
/platforms — Manage connected social platforms
/models — View available AI models for each pipeline step
/cancel [job_id] — Cancel a running or queued job
/history — View last 10 completed jobs with video links
/settings — Configure default preferences
/help — Show all commands

"""

#  /start
@dp.message(Command("start"))
async def cmd_start(message: aiogram_types.Message, state: FSMContext):
    await state.clear()
    await message.reply(
        "👋 <b>Welcome to Omni Bot!</b>\n\n"
        "I can help you with:\n"
        "🎬 Video Downloader\n"
        "🖼️ Image generation\n"
        "🔧 Video generation\n"
        "🎙️ Audio transcription\n"
        "📤 YouTube upload automation\n\n"
        "Type /help for all commands.",
        parse_mode="HTML"
    )

#  /chat
@dp.message(Command("chat"))
async def cmd_chat(message: aiogram_types.Message, state: FSMContext):
    await state.clear()
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Nemotron 30B", callback_data="chat_model:nemotron")],
        [InlineKeyboardButton(text="🧠 DeepSeek V3.2", callback_data="chat_model:deepseek")]
    ])
    
    await message.answer(
        "💬 <b>Chat mode</b>\nWhich AI model would you like to chat with?",
        parse_mode="HTML",
        reply_markup=markup
    )

@dp.callback_query(F.data.startswith("chat_model:"))
async def receive_chat_model(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    model_choice = callback.data.split(":")[1]
    
    await state.update_data(chat_model=model_choice)
    await state.set_state(BotStates.chatting)
    
    model_name = "Nemotron 30B" if model_choice == "nemotron" else "DeepSeek V3.2"
    
    await callback.message.edit_text(
        f"💬 <b>Chat mode active! ({model_name})</b>\nAsk me anything about the project.\n"
        "Send any command to exit chat mode.",
        parse_mode="HTML"
    )

@dp.message(BotStates.chatting)
async def receive_chat_message(message: aiogram_types.Message, state: FSMContext):
    if await cancel_if_command(message, state, resume_command="/chat"):
        return
        
    data = await state.get_data()
    model = data.get("chat_model", "nemotron")
    
    if model == "deepseek":
        await deepseek_AI_chatting(message, SYSTEM_INSTRUCTION, nvidia_chat_client_2)
    else:
        await nvidia_AI_chatting(message, SYSTEM_INSTRUCTION, nvidia_chat_client_1)


# ═══════════════════════════════════════════════════════════════
#  /downloader — unified entry (YouTube, Instagram, Twitter/X, …)
# ═══════════════════════════════════════════════════════════════
@dp.message(Command("downloader"))
async def cmd_downloader(
    message: aiogram_types.Message,
    command: CommandObject,
    state: FSMContext,
):
    await state.clear()

    if command.args:
        video_url = command.args.strip()
        # Quick URL format check
        if not video_url.startswith(("http://", "https://")):
            await message.answer(
                "⚠️ That doesn't look like a valid URL.\n"
                "Please provide a full link starting with <code>https://</code>",
                parse_mode="HTML",
            )
            return
        # Validate with yt-dlp
        valid, info = validate_video_url(video_url)
        if not valid:
            await message.answer(
                "❌ <b>This URL is not a supported video link.</b>\n\n"
                "I support YouTube, Instagram, Twitter/X, TikTok, and "
                "<b>1 000+ other video platforms</b>.\n\n"
                f"<code>{info[:200]}</code>",
                parse_mode="HTML",
            )
            return
        await state.update_data(url=video_url)
        await _fetch_and_show_qualities(
            message, state, video_url, WARN_SIZE_BYTES,
            BotStates.dl_waiting_for_quality,
        )
        return

    await state.set_state(BotStates.dl_waiting_for_url)
    await message.answer(
        "📥 <b>Video Downloader</b>\n\n"
        "Send me a video URL from <b>YouTube, Instagram, Twitter/X, "
        "TikTok</b>, or any other supported platform.\n\n"
        "<i>Examples:</i>\n"
        "<code>https://www.youtube.com/watch?v=abcd</code>\n"
        "<code>https://www.instagram.com/reel/ABC123/</code>\n"
        "<code>https://x.com/user/status/123456</code>",
        parse_mode="HTML",
    )


@dp.message(BotStates.dl_waiting_for_url)
async def receive_download_url(message: aiogram_types.Message, state: FSMContext):
    if await cancel_if_command(message, state, resume_command="/downloader"):
        return

    video_url = (message.text or "").strip()
    if not video_url.startswith(("http://", "https://")):
        await message.answer(
            "⚠️ That doesn't look like a valid URL.\n"
            "Please send a full video link starting with <code>https://</code>",
            parse_mode="HTML",
        )
        return

    # Validate with yt-dlp
    valid, info = validate_video_url(video_url)
    if not valid:
        await message.answer(
            "❌ <b>This URL is not a supported video link.</b>\n\n"
            "I support YouTube, Instagram, Twitter/X, TikTok, and "
            "<b>1 000+ other video platforms</b>.\n\n"
            f"<code>{info[:200]}</code>",
            parse_mode="HTML",
        )
        return

    await state.update_data(url=video_url)
    await _fetch_and_show_qualities(
        message, state, video_url, WARN_SIZE_BYTES,
        BotStates.dl_waiting_for_quality,
    )


# ═══════════════════════════════════════════════════════════════
#  /downloader — quality selected
#
#  file_size ≤ 50 MB  →  send directly via Telegram
#  file_size  > 50 MB →  upload to gofile.io → send link
# ═══════════════════════════════════════════════════════════════
@dp.callback_query(BotStates.dl_waiting_for_quality, F.data.startswith("dl_quality:"))
async def receive_quality_choice(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    choice = callback.data.split(":", 1)[1]

    if choice == "cancel":
        await callback.message.edit_text("❌ Download cancelled.")
        await state.clear()
        return

    data      = await state.get_data()
    video_url = data.get("url")
    if not video_url:
        await callback.message.edit_text("⚠️ Session expired. Please use /downloader again.")
        await state.clear()
        return

    await state.clear()

    quality_label = "Audio Only (MP3)" if choice == "audio_only" else f"quality {choice}"
    status_msg = await callback.message.edit_text(
        f"⬇️ <b>Downloading...</b>  [{quality_label}]\n"
        "This may take a moment depending on file size.",
        parse_mode="HTML",
    )

    # ── Download the file ─────────────────────────────────────
    try:
        loop     = asyncio.get_running_loop()
        filepath = await loop.run_in_executor(
            None, download_video, video_url, choice, str(DOWNLOAD_DIR),
        )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Download failed.</b>\n\n<code>{str(e)[:300]}</code>",
            parse_mode="HTML",
        )
        return

    file_size = filepath.stat().st_size
    size_mb   = file_size / 1_048_576

    try:
        if file_size <= TELEGRAM_MAX_BYTES:
            await status_msg.edit_text(
                f"📤 <b>Uploading to Telegram...</b>  ({size_mb:.1f} MB)",
                parse_mode="HTML",
            )
            if choice == "audio_only":
                await callback.message.answer_audio(
                    audio=FSInputFile(filepath),
                    caption=f"🎵 Here's your audio!  ({size_mb:.1f} MB)",
                )
            else:
                await callback.message.answer_video(
                    video=FSInputFile(filepath),
                    caption=f"🎬 Here's your video!  ({size_mb:.1f} MB)",
                    supports_streaming=True,
                )
            await status_msg.delete()

        else:
            await status_msg.edit_text(
                f"📦 <b>File is {size_mb:.1f} MB</b> — too large for Telegram.\n"
                "☁️ Uploading to gofile.io, please wait...",
                parse_mode="HTML",
            )
            download_link = await upload_to_gofile_async(filepath)
            await status_msg.edit_text(
                f"✅ <b>Your file is ready!</b>\n\n"
                f"📦 <b>Size:</b> {size_mb:.1f} MB\n"
                f"🔗 <a href='{download_link}'>Click here to download</a>\n\n"
                "<i>Hosted on gofile.io — expires after 10 days of inactivity.</i>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Failed to deliver file.</b>\n<code>{str(e)[:200]}</code>",
            parse_mode="HTML",
        )
    finally:
        filepath.unlink(missing_ok=True)

# ═══════════════════════════════════════════════════════════════
#  /generateVideo
# ═══════════════════════════════════════════════════════════════
@dp.message(Command("generateVideo"))
async def cmd_generate_video(
    message: aiogram_types.Message,
    command: CommandObject,
    state: FSMContext,
):
    await state.clear()

    if command.args:
        topic = command.args.strip()
        await start_video_generation(message, topic, STORAGE_DIR, LTX_API_URL)
        return

    await state.set_state(BotStates.Video_prompt)
    await message.answer(
        "🎬 <b>Video Generation</b>\n\n"
        "What should this cartoon be about?\n\n"
        "<b>Examples:</b>\n"
        "• A dragon who learns to be friends with a knight\n"
        "• A space adventure with talking animals\n"
        f"• {DEFAULT_VID_TOPIC}\n\n"
        "<i>Type your idea below 👇</i>",
        parse_mode="HTML"
    )

@dp.message(BotStates.Video_prompt)
async def receive_video_topic(message: aiogram_types.Message, state: FSMContext):
    if await cancel_if_command(message, state, resume_command="/generateVideo"):
        return
    topic = (message.text or "").strip()
    if not topic:
        await message.answer("Please enter a topic.")
        return
    await state.clear()
    await start_video_generation(message, topic, STORAGE_DIR, LTX_API_URL)

# ═══════════════════════════════════════════════════════════════
#  /transcribe
# ═══════════════════════════════════════════════════════════════
@dp.message(Command("transcribe"))
async def cmd_transcribe(message: aiogram_types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BotStates.transcribe_waiting)
    await message.answer(
        "🎙️ <b>Audio Transcription</b>\n\n"
        "Please send me a <b>voice note</b> or an <b>audio file</b> to transcribe.\n"
        "I will provide the full text and a concise summary.",
        parse_mode="HTML"
    )

@dp.message(BotStates.transcribe_waiting, F.voice | F.audio)
async def receive_transcription_audio(message: aiogram_types.Message, state: FSMContext):
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    await state.clear()
    await process_transcription(message, file_id, bot, whisper_client, nvidia_chat_client_1)

@dp.message(BotStates.transcribe_waiting)
async def invalid_transcription_input(message: aiogram_types.Message):
    await message.answer("⚠️ Please send an <b>audio file</b> or a <b>voice note</b>.")

# ═══════════════════════════════════════════════════════════════
#  /generateAudio
# ═══════════════════════════════════════════════════════════════
@dp.message(Command("generateAudio"))
async def cmd_generate_audio(
    message: aiogram_types.Message,
    command: CommandObject,
    state: FSMContext,
):
    await state.clear()

    if command.args:
        prompt = command.args.strip()
        await start_audio_generation(message, prompt, STORAGE_DIR)
        return

    await state.set_state(BotStates.Audio_prompt)
    tags_list = (
        "• <code>[laughs]</code>\n"
        "• <code>[sighs]</code>\n"
        "• <code>[music]</code>\n"
        "• <code>[clears throat]</code>\n"
        "• <code>[hesitation]</code>\n"
        "• <code>—</code> or <code>...</code> (for pauses)\n"
    )
    await message.answer(
        "🎙️ <b>Audio Generation (Suno Bark)</b>\n\n"
        "Send me a <b>script</b> or an <b>audio message</b> (I'll transcribe it first).\n\n"
        f"<b>Non-speech tags you can use:</b>\n{tags_list}\n"
        "<b>Example:</b>\n"
        "<i>\"Hello! [clears throat] Uh... I'm really [laughs] happy to be here! [music]\"</i>\n\n"
        "<i>Type your script or send a voice note below 👇</i>",
        parse_mode="HTML"
    )

@dp.message(BotStates.Audio_prompt, F.voice | F.audio)
async def receive_audio_input(message: aiogram_types.Message, state: FSMContext):
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    await state.clear()
    
    status_msg = await message.answer("⏳ <b>Transcribing your voice...</b>", parse_mode="HTML")
    
    # Download and transcribe
    temp_dir = Path("temp_transcriptions")
    temp_dir.mkdir(exist_ok=True)
    file_info = await bot.get_file(file_id)
    file_path = temp_dir / Path(file_info.file_path).name
    
    try:
        await bot.download_file(file_info.file_path, destination=file_path)
        transcript = await transcribe_audio(file_path, whisper_client)
        
        if not transcript or not transcript.strip():
            await status_msg.edit_text("❌ Could not transcribe audio.")
            return
            
        await status_msg.delete()
        await start_audio_generation(message, transcript.strip(), STORAGE_DIR)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Error:</b> <code>{e}</code>", parse_mode="HTML")
    finally:
        file_path.unlink(missing_ok=True)

@dp.message(BotStates.Audio_prompt)
async def receive_audio_prompt(message: aiogram_types.Message, state: FSMContext):
    if await cancel_if_command(message, state, resume_command="/generateAudio"):
        return
    prompt = (message.text or "").strip()
    if not prompt:
        await message.answer("Please enter some text or send audio.")
        return
    await state.clear()
    await start_audio_generation(message, prompt, STORAGE_DIR)

# ═══════════════════════════════════════════════════════════════
#  /generateImage  (prompt → aspect ratio → quality → neg prompt)
# ═══════════════════════════════════════════════════════════════
@dp.message(Command("generateImage"))
async def cmd_generate_image(
    message: aiogram_types.Message,
    command: CommandObject,
    state: FSMContext,
):
    await state.clear()

    if command.args:
        # Inline: /generateImage <prompt> — store & jump to aspect ratio
        await state.update_data(img_prompt=command.args.strip())
        await state.set_state(BotStates.Image_aspect_ratio)
        await message.answer(
            "📐 <b>Choose an aspect ratio:</b>",
            parse_mode="HTML",
            reply_markup=build_aspect_ratio_keyboard(),
        )
        return

    await state.set_state(BotStates.Image_prompt)
    await message.answer(
        "🖼️ <b>Image Generation</b>\n\n"
        "Describe the image you want to create.\n\n"
        "<b>Examples:</b>\n"
        "• A futuristic cityscape at sunset\n"
        "• A cute dragon sitting on a pile of gold coins\n"
        "• Vintage steampunk-inspired airship above a Victorian city\n\n"
        "<i>Type your prompt below 👇</i>",
        parse_mode="HTML",
    )

# Step 1 — receive prompt text
@dp.message(BotStates.Image_prompt)
async def receive_image_prompt(message: aiogram_types.Message, state: FSMContext):
    if await cancel_if_command(message, state, resume_command="/generateImage"):
        return
    prompt = (message.text or "").strip()
    if not prompt:
        await message.answer("Please enter a prompt for the image.")
        return
    await state.update_data(img_prompt=prompt)
    await state.set_state(BotStates.Image_aspect_ratio)
    await message.answer(
        "📐 <b>Choose an aspect ratio:</b>",
        parse_mode="HTML",
        reply_markup=build_aspect_ratio_keyboard(),
    )

# Step 2 — aspect ratio selected
@dp.callback_query(BotStates.Image_aspect_ratio, F.data.startswith("img_ar:"))
async def receive_image_aspect_ratio(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    choice = callback.data.split(":", 1)[1]
    if choice == "cancel":
        await callback.message.edit_text("❌ Image generation cancelled.")
        await state.clear()
        return
    await state.update_data(img_aspect_ratio=choice)
    await state.set_state(BotStates.Image_quality)
    await callback.message.edit_text(
        "⚙️ <b>Select image quality:</b>",
        parse_mode="HTML",
        reply_markup=build_img_quality_keyboard(),
    )

# Step 3 — quality selected
@dp.callback_query(BotStates.Image_quality, F.data.startswith("img_quality:"))
async def receive_image_quality(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    choice = callback.data.split(":", 1)[1]
    if choice == "cancel":
        await callback.message.edit_text("❌ Image generation cancelled.")
        await state.clear()
        return
    await state.update_data(img_quality=choice)
    await state.set_state(BotStates.Image_negative)
    await callback.message.edit_text(
        "🚫 <b>Negative prompt</b> (optional)\n\n"
        "Describe what you <b>don't</b> want in the image.\n\n"
        "<i>Examples: blurry, low quality, watermark, text, extra fingers</i>\n\n"
        "Type below or tap <b>Skip</b> to continue without one.",
        parse_mode="HTML",
        reply_markup=build_neg_prompt_keyboard(),
    )

# Step 4a — negative prompt skipped via button
@dp.callback_query(BotStates.Image_negative, F.data.startswith("img_neg:"))
async def receive_neg_prompt_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    choice = callback.data.split(":", 1)[1]
    if choice == "cancel":
        await callback.message.edit_text("❌ Image generation cancelled.")
        await state.clear()
        return
    # "skip" — generate with no negative prompt
    await callback.message.edit_text("✅ Starting generation...")
    data = await state.get_data()
    await state.clear()
    await generate_image(
        callback.message,
        prompt=data.get("img_prompt", ""),
        aspect_ratio=data.get("img_aspect_ratio", "16:9"),
        quality_key=data.get("img_quality", "balanced"),
        negative_prompt="",
    )

# Step 4b — negative prompt typed as text
@dp.message(BotStates.Image_negative)
async def receive_neg_prompt_text(message: aiogram_types.Message, state: FSMContext):
    if await cancel_if_command(message, state, resume_command="/generateImage"):
        return
    neg = (message.text or "").strip()
    data = await state.get_data()
    await state.clear()
    await generate_image(
        message,
        prompt=data.get("img_prompt", ""),
        aspect_ratio=data.get("img_aspect_ratio", "16:9"),
        quality_key=data.get("img_quality", "balanced"),
        negative_prompt=neg,
    )

#  /help
@dp.message(Command("help"))
async def cmd_help(message: aiogram_types.Message, state: FSMContext):
    await state.clear()
    await message.answer(HELP_TEXT, parse_mode="HTML")

#  FALLBACK — plain text, no active FSM state
@dp.message(F.text & ~F.text.startswith("/"))
async def handle_no_state_text(message: aiogram_types.Message, state: FSMContext):
    if await state.get_state() is not None:
        return

    text = (message.text or "").strip()

    # Auto-detect video URLs and download directly (best quality)
    if _URL_RE.match(text):
        valid, _ = validate_video_url(text)
        if valid:
            await cmd_direct_download(message, text)
            return

    await message.answer(
        "💬 It looks like you want to chat!\n"
        "Use /chat to start a conversation with me.\n"
        "Or Use /help to see all commands."
    )

async def handle_ping(reader, writer):
    # Simple HTTP 200 OK response for Render's health check
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
    await writer.drain()
    writer.close()

#  ENTRY POINT — graceful shutdown
async def main():
    # Start a dummy HTTP server on PORT for Render's Web Service requirements
    port = int(os.environ.get("PORT", 10000))
    server = await asyncio.start_server(handle_ping, '0.0.0.0', port)
    
    # Run the dummy server in the background
    asyncio.create_task(server.serve_forever())
    print(f"✅ Dummy HTTP server listening on port {port} for Render")

    try:
        await dp.start_polling(bot, handle_signals=True)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await bot.session.close()
        print("✅ Bot stopped gracefully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass