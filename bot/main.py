import os
import re
import asyncio
import yt_dlp
import requests
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
from handlers.chat import groq_AI_chatting
from utilities import cancel_if_command, upload_to_gofile_async
from handlers.ytDownloader import download_video, fetch_formats, build_quality_keyboard, _fetch_and_show_qualities
from handlers.generateVideo import start_video_generation
from handlers.directDownloader import cmd_yt_downloader, cmd_insta_downloader

# ── URL patterns for YouTube & Instagram ──────────────────────
_YT_RE = re.compile(
    r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/?\S*",
    re.IGNORECASE,
)
_IG_RE = re.compile(
    r"https?://(?:www\.|m\.)?instagram\.com/\S*",
    re.IGNORECASE,
)

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
# openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#  FSM STATE GROUP
class BotStates(StatesGroup):
    chatting            = State()   # /chat flow
    waiting_for_url     = State()   # /ytDownloader — step 1
    waiting_for_quality = State()   # /ytDownloader — step 2
    Video_prompt        = State()   # /generateVideo — step 1
    Audio_prompt        = State()   # /generateVideo — step 2
    Image_prompt        = State()   # /generateVideo — step 3

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
You are an AI assistant for a Fully Automated Kids Cartoon Generator & YouTube Auto-Uploader project.

The pipeline of this project is:
1. Topic/Theme Input (or auto-generated topics)
2. AI Script Generation (Claude/GPT)
3. Image Generation per scene (DALL-E 3 / Stable Diffusion / Imagen)
4. Image → Video conversion (Veo / Runway ML / Pika Labs)
5. AI Voiceover Generation (ElevenLabs / Google TTS)
6. Background Music Addition (royalty-free)
7. FFmpeg: Assemble scenes + audio into final video
8. AI-generated Title, Description, Tags, Thumbnail
9. Auto-upload to YouTube with scheduling
10. Telegram notification on completion

Available bot commands the user can use:
/start — Initialize the bot and authenticate
/chat — General chat with the AI assistant
/ytDownloader — Download a video from YouTube by providing a link
/instaDownloader — Download a video from Instagram by providing a link
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
/ytDownloader — Download a YouTube video (choose quality)
/instaDownloader — Download a video from Instagram by providing a link
/generateAudio — Generate a single audio clip from a prompt
/generateImage — Generate a single image from a prompt
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
        "👋 <b>Welcome to the AI Kids Cartoon Generator Bot!</b>\n\n"
        "I can help you with:\n"
        "🎬 Script writing & video generation\n"
        "🖼️ Scene & image prompts\n"
        "🔧 Pipeline code & setup\n"
        "📤 YouTube upload automation\n\n"
        "Type /generateVideo to create a video, or /help for all commands.",
        parse_mode="HTML"
    )

#  /chat
@dp.message(Command("chat"))
async def cmd_chat(message: aiogram_types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BotStates.chatting)
    await message.answer(
        "💬 <b>Chat mode active!</b>\nAsk me anything about the project.\n"
        "Send any command to exit chat mode.",
        parse_mode="HTML"
    )

@dp.message(BotStates.chatting)
async def receive_chat_message(message: aiogram_types.Message, state: FSMContext):
    if await cancel_if_command(message, state, resume_command="/chat"):
        return
    await groq_AI_chatting(message, SYSTEM_INSTRUCTION, client)


# ═══════════════════════════════════════════════════════════════
#  /ytDownloader — entry
# ═══════════════════════════════════════════════════════════════
@dp.message(Command("ytDownloader"))
async def cmd_downloader(
    message: aiogram_types.Message,
    command: CommandObject,
    state: FSMContext,
):
    await state.clear()

    if command.args:
        video_url = command.args.strip()
        await state.update_data(url=video_url)
        await _fetch_and_show_qualities(message, state, video_url, WARN_SIZE_BYTES, BotStates)
        return

    await state.set_state(BotStates.waiting_for_url)
    await message.answer(
        "📥 <b>YouTube Downloader</b>\n\n"
        "Please send the YouTube video URL you want to download.\n\n"
        "<i>Example:</i>\n"
        "<code>https://www.youtube.com/watch?v=abcd</code>",
        parse_mode="HTML"
    )

@dp.message(BotStates.waiting_for_url)
async def receive_download_url(message: aiogram_types.Message, state: FSMContext):
    if await cancel_if_command(message, state, resume_command="/ytDownloader"):
        return

    video_url = (message.text or "").strip()
    if not video_url.startswith(("http://", "https://")):
        await message.answer(
            "⚠️ That doesn't look like a valid URL.\n"
            "Please send a full YouTube link starting with <code>https://</code>",
            parse_mode="HTML"
        )
        return

    await state.update_data(url=video_url)
    await _fetch_and_show_qualities(message, state, video_url, WARN_SIZE_BYTES, BotStates)


# ═══════════════════════════════════════════════════════════════
#  /ytDownloader — quality selected
#
#  After download, decision tree:
#
#  file_size ≤ 50 MB  →  send directly via Telegram
#  file_size  > 50 MB →  upload to gofile.io → send link
# ═══════════════════════════════════════════════════════════════
@dp.callback_query(BotStates.waiting_for_quality, F.data.startswith("dl_quality:"))
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
        await callback.message.edit_text("⚠️ Session expired. Please use /ytDownloader again.")
        await state.clear()
        return

    await state.clear()

    quality_label = "Audio Only (MP3)" if choice == "audio_only" else f"quality {choice}"
    status_msg = await callback.message.edit_text(
        f"⬇️ <b>Downloading...</b>  [{quality_label}]\n"
        "This may take a moment depending on file size.",
        parse_mode="HTML"
    )

    # ── Download the file ─────────────────────────────────────
    try:
        loop     = asyncio.get_running_loop()
        filepath = await loop.run_in_executor(
            None, download_video, video_url, choice, str(DOWNLOAD_DIR)
        )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Download failed.</b>\n\n<code>{str(e)[:300]}</code>",
            parse_mode="HTML"
        )
        return

    file_size = filepath.stat().st_size
    size_mb   = file_size / 1_048_576

    try:
        if file_size <= TELEGRAM_MAX_BYTES:
            # ── Under 50 MB: send directly to Telegram ───────
            await status_msg.edit_text(
                f"📤 <b>Uploading to Telegram...</b>  ({size_mb:.1f} MB)",
                parse_mode="HTML"
            )
            if choice == "audio_only":
                await callback.message.answer_audio(
                    audio=FSInputFile(filepath),
                    caption=f"🎵 Here's your audio!  ({size_mb:.1f} MB)"
                )
            else:
                await callback.message.answer_video(
                    video=FSInputFile(filepath),
                    caption=f"🎬 Here's your video!  ({size_mb:.1f} MB)",
                    supports_streaming=True
                )
            await status_msg.delete()

        else:
            # ── Over 50 MB: upload to gofile.io, send link ───
            await status_msg.edit_text(
                f"📦 <b>File is {size_mb:.1f} MB</b> — too large for Telegram.\n"
                "☁️ Uploading to gofile.io, please wait...",
                parse_mode="HTML"
            )
            download_link = await upload_to_gofile_async(filepath)
            await status_msg.edit_text(
                f"✅ <b>Your file is ready!</b>\n\n"
                f"📦 <b>Size:</b> {size_mb:.1f} MB\n"
                f"🔗 <a href='{download_link}'>Click here to download</a>\n\n"
                "<i>Hosted on gofile.io — expires after 10 days of inactivity.</i>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )

    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Failed to deliver file.</b>\n<code>{str(e)[:200]}</code>",
            parse_mode="HTML"
        )
    finally:
        filepath.unlink(missing_ok=True)   # always delete local file

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
    
    video_url = (message.text or "").strip()
    if _YT_RE.match(video_url):
        await cmd_yt_downloader(message, video_url)
    elif _IG_RE.match(video_url):
        await cmd_insta_downloader(message, video_url)
    else:
        await message.answer(
            "💬 It looks like you want to chat!\n"
            "Use /chat to start a conversation with me."
        )

#  ENTRY POINT — graceful shutdown
async def main():
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