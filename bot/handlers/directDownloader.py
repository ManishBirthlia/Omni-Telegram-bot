import asyncio
from pathlib import Path
from aiogram import types as aiogram_types
from aiogram.types import FSInputFile
import yt_dlp

# ═══════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════
YOUTUBE_DIR   = Path("Youtube Downloads")
INSTAGRAM_DIR = Path("Instagram Downloads")
YOUTUBE_DIR.mkdir(exist_ok=True)
INSTAGRAM_DIR.mkdir(exist_ok=True)

TELEGRAM_MAX_BYTES = 50 * 1024 * 1024   # 50 MB


# ═══════════════════════════════════════════════════════════════
#  HELPER — download best quality with yt-dlp
#
#  yt-dlp natively supports YouTube AND Instagram URLs.
#  "bestvideo+bestaudio/best" grabs the highest quality available.
# ═══════════════════════════════════════════════════════════════
def _download_best(url: str, out_dir: str) -> Path:
    output_template = str(Path(out_dir) / "%(title)s.%(ext)s")

    ydl_opts = {
        "format":              "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl":             output_template,
        "quiet":               True,
        "no_warnings":         True,
        # Instagram sometimes needs cookies / login — yt-dlp handles public posts fine
        "socket_timeout":      30,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info     = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    return Path(filename).with_suffix(".mp4"), info


# ═══════════════════════════════════════════════════════════════
#  HELPER — gofile upload (reuse from utilities)
# ═══════════════════════════════════════════════════════════════
async def _upload_to_gofile(filepath: Path) -> str:
    import requests

    def _upload(fp: Path) -> str:
        server_resp = requests.get("https://api.gofile.io/servers", timeout=15)
        server_resp.raise_for_status()
        servers = server_resp.json().get("data", {}).get("servers", [])
        if not servers:
            raise RuntimeError("gofile.io returned no available servers.")
        server_name = servers[0]["name"]

        upload_url = f"https://{server_name}.gofile.io/uploadFile"
        with open(fp, "rb") as f:
            upload_resp = requests.post(
                upload_url,
                files={"file": (fp.name, f)},
                timeout=300,
            )
        upload_resp.raise_for_status()
        data = upload_resp.json()
        if data.get("status") != "ok":
            raise RuntimeError(f"gofile.io upload failed: {data}")
        return data["data"]["downloadPage"]

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _upload, filepath)


# ═══════════════════════════════════════════════════════════════
#  HELPER — deliver file to user (Telegram or gofile link)
# ═══════════════════════════════════════════════════════════════
async def _deliver_file(
    message: aiogram_types.Message,
    filepath: Path,
    status_msg: aiogram_types.Message,
    title: str,
):
    file_size = filepath.stat().st_size
    size_mb   = file_size / 1_048_576

    try:
        if file_size <= TELEGRAM_MAX_BYTES:
            await status_msg.edit_text(
                f"📤 <b>Uploading to Telegram...</b>  ({size_mb:.1f} MB)",
                parse_mode="HTML",
            )
            await message.answer_video(
                video=FSInputFile(filepath),
                caption=f"🎬 <b>{title}</b>\n📦 {size_mb:.1f} MB",
                supports_streaming=True,
                parse_mode="HTML",
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text(
                f"📦 <b>File is {size_mb:.1f} MB</b> — too large for Telegram.\n"
                "☁️ Uploading to gofile.io, please wait...",
                parse_mode="HTML",
            )
            download_link = await _upload_to_gofile(filepath)
            await status_msg.edit_text(
                f"✅ <b>Your file is ready!</b>\n\n"
                f"🎬 <b>{title}</b>\n"
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
        # Uncomment the line below to delete local files after delivery:
        # filepath.unlink(missing_ok=True)
        pass


# ═══════════════════════════════════════════════════════════════
#  PUBLIC — YouTube direct download (best quality)
# ═══════════════════════════════════════════════════════════════
async def cmd_yt_downloader(message: aiogram_types.Message, url: str):
    status_msg = await message.answer(
        "⬇️ <b>Downloading YouTube video</b> (best quality)...\n"
        "This may take a moment depending on file size.",
        parse_mode="HTML",
    )

    try:
        loop = asyncio.get_running_loop()
        filepath, info = await loop.run_in_executor(
            None, _download_best, url, str(YOUTUBE_DIR)
        )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Download failed.</b>\n\n<code>{str(e)[:300]}</code>",
            parse_mode="HTML",
        )
        return

    title = info.get("title", "YouTube Video")
    await _deliver_file(message, filepath, status_msg, title)


# ═══════════════════════════════════════════════════════════════
#  PUBLIC — Instagram direct download (best quality)
# ═══════════════════════════════════════════════════════════════
async def cmd_insta_downloader(message: aiogram_types.Message, url: str):
    status_msg = await message.answer(
        "⬇️ <b>Downloading Instagram video</b> (best quality)...\n"
        "This may take a moment.",
        parse_mode="HTML",
    )

    try:
        loop = asyncio.get_running_loop()
        filepath, info = await loop.run_in_executor(
            None, _download_best, url, str(INSTAGRAM_DIR)
        )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Download failed.</b>\n\n<code>{str(e)[:300]}</code>\n\n"
            "<i>Note: Private Instagram posts cannot be downloaded.</i>",
            parse_mode="HTML",
        )
        return

    title = info.get("title", "Instagram Video")
    await _deliver_file(message, filepath, status_msg, title)