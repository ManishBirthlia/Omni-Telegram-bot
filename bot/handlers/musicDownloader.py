import os
import shutil
import asyncio
import uuid
import subprocess
from pathlib import Path
from aiogram.types import FSInputFile, Message
from utilities import upload_to_gofile_async

TELEGRAM_MAX_BYTES = 50 * 1024 * 1024   # 50 MB

async def process_music_download(message: Message, url: str, base_dir: Path):
    """
    Handles downloading music via spotdl and sending the file back.
    """
    status_msg = await message.answer(
        "🎵 <b>Initializing spotdl...</b>\nDownloading track & embedding metadata.",
        parse_mode="HTML"
    )
    
    # Create temp unique dir for this specific job to easily find the downloaded file
    job_id = str(uuid.uuid4())
    temp_dir = base_dir / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Run spotdl in subprocess
        loop = asyncio.get_running_loop()
        
        # Build command: spotdl <url> --output <dir>
        # Additional formatting ensures safe filenames. 
        # --format mp3 is default but good to be explicit occasionally.
        cmd = ["spotdl", url, "--output", str(temp_dir), "--format", "mp3"]
        
        def run_spotdl():
            # capture_output to prevent spamming the console
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                raise Exception(f"spotdl failed:\n{result.stderr or result.stdout}")
        
        await loop.run_in_executor(None, run_spotdl)
        
        # Find the downloaded file
        files = list(temp_dir.glob("*.mp3")) + list(temp_dir.glob("*.m4a")) + list(temp_dir.glob("*.opus"))
        if not files:
            raise Exception("Download succeeded but no audio file was found.")
        
        audio_file = files[0]
        file_size = audio_file.stat().st_size
        size_mb = file_size / 1_048_576
        
        if file_size <= TELEGRAM_MAX_BYTES:
            await status_msg.edit_text(
                f"📤 <b>Uploading to Telegram...</b>  ({size_mb:.1f} MB)",
                parse_mode="HTML"
            )
            await message.bot.send_audio(
                chat_id=message.chat.id,
                audio=FSInputFile(audio_file),
                caption=f"🎵 Here is your downloaded track! ({size_mb:.1f} MB)"
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text(
                f"📦 <b>File is {size_mb:.1f} MB</b> — too large for Telegram.\n"
                "☁️ Uploading to gofile.io, please wait...",
                parse_mode="HTML"
            )
            download_link = await upload_to_gofile_async(audio_file)
            await status_msg.edit_text(
                f"✅ <b>Your track is ready!</b>\n\n"
                f"📦 <b>Size:</b> {size_mb:.1f} MB\n"
                f"🔗 <a href='{download_link}'>Click here to download</a>\n\n"
                "<i>Hosted on gofile.io — expires after 10 days of inactivity.</i>",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        await status_msg.edit_text(
            f"❌ <b>Download failed.</b>\n<code>{error_msg}</code>",
            parse_mode="HTML"
        )
    finally:
        # Cleanup the temp dir
        shutil.rmtree(temp_dir, ignore_errors=True)
