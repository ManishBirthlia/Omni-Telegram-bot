from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pathlib import Path
import asyncio
import yt_dlp

# ═══════════════════════════════════════════════════════════════
#  VIDEO DOWNLOADER — URL validation
#
#  Uses yt-dlp's own extractors to decide whether a URL is a
#  downloadable video.  Returns (True, extractor_key) on success
#  or (False, error_string) on failure.
# ═══════════════════════════════════════════════════════════════
def validate_video_url(url: str) -> tuple[bool, str]:
    """
    Probe *url* with yt-dlp in simulate mode (no download).
    Returns (True, extractor_name)  — URL is a valid video
            (False, error_message)  — URL is NOT supported / not a video
    """
    ydl_opts = {
        "quiet":       True,
        "no_warnings": True,
        "skip_download": True,
        # Don't actually download anything — just probe
        "simulate":    True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            return False, "yt-dlp returned no info for this URL."

        # yt-dlp uses "Generic" extractor for random pages (HTML with
        # an embedded <video> tag, direct .mp4 links, etc.).
        # We allow Generic only if it actually found a video format.
        extractor = info.get("extractor_key") or info.get("extractor") or "Generic"

        # For playlists yt-dlp returns _type="playlist" — we only want
        # single-video URLs for this flow.
        if info.get("_type") == "playlist":
            # Pick the first entry's extractor if available
            entries = info.get("entries")
            if entries:
                first = next(iter(entries), None)
                if first:
                    extractor = first.get("extractor_key") or extractor

        return True, extractor

    except yt_dlp.utils.DownloadError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════════════════════════
#  VIDEO DOWNLOADER — quality keyboard
#
#  Labels show estimated size.
#  Anything estimated over WARN_SIZE_BYTES gets "⚠️ Via link"
#  so the user knows upfront it will arrive as a gofile link.
# ═══════════════════════════════════════════════════════════════
def build_quality_keyboard(formats: list[dict], WARN_SIZE_BYTES: int) -> InlineKeyboardMarkup:
    buttons = []
    seen    = set()

    for f in formats:
        height   = f.get("height")
        fmt_id   = f.get("format_id", "")
        ext      = f.get("ext", "mp4")
        filesize = f.get("filesize") or f.get("filesize_approx") or 0
        fps      = f.get("fps") or 0

        if not height or fmt_id in seen:
            continue

        label = f"{height}p"
        if fps and fps >= 60:
            label += f" {int(fps)}fps"
        label += f"  [{ext.upper()}]"

        if filesize:
            size_mb = filesize / 1_048_576
            label  += f"  ~{size_mb:.1f} MB"
            if filesize > WARN_SIZE_BYTES:
                label += "  ⚠️ Via link"

        seen.add(fmt_id)
        buttons.append(
            InlineKeyboardButton(text=label, callback_data=f"dl_quality:{fmt_id}")
        )

    buttons.append(InlineKeyboardButton(text="🎵  Audio Only  [MP3]", callback_data="dl_quality:audio_only"))
    buttons.append(InlineKeyboardButton(text="❌  Cancel",             callback_data="dl_quality:cancel"))

    return InlineKeyboardMarkup(inline_keyboard=[[btn] for btn in buttons])


# ═══════════════════════════════════════════════════════════════
#  VIDEO DOWNLOADER — fetch formats (metadata only)
# ═══════════════════════════════════════════════════════════════
def fetch_formats(video_url: str) -> tuple[list[dict], dict]:
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

    formats = info.get("formats", [])
    video_formats = [
        f for f in formats
        if f.get("height") and f.get("vcodec") != "none"
    ]
    video_formats.sort(key=lambda f: f.get("height", 0), reverse=True)

    seen_heights: dict[int, dict] = {}
    for f in video_formats:
        h = f["height"]
        if h not in seen_heights:
            seen_heights[h] = f
        elif f.get("ext") == "mp4":
            seen_heights[h] = f

    return list(seen_heights.values()), info


# ═══════════════════════════════════════════════════════════════
#  VIDEO DOWNLOADER — actual file download
# ═══════════════════════════════════════════════════════════════
def download_video(video_url: str, format_id: str, out_dir) -> Path:
    out_dir         = Path(out_dir)
    output_template = str(out_dir / "%(title)s.%(ext)s")

    if format_id == "audio_only":
        ydl_opts = {
            "format":         "bestaudio/best",
            "outtmpl":        output_template,
            "quiet":          True,
            "no_warnings":    True,
            "postprocessors": [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "mp3",
                "preferredquality": "192",
            }],
        }
    else:
        ydl_opts = {
            "format":              f"{format_id}+bestaudio/{format_id}",
            "outtmpl":             output_template,
            "quiet":               True,
            "no_warnings":         True,
            "merge_output_format": "mp4",
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info     = ydl.extract_info(video_url, download=True)
        filename = ydl.prepare_filename(info)

    path = Path(filename)
    if format_id == "audio_only":
        path = path.with_suffix(".mp3")
    return path


# ═══════════════════════════════════════════════════════════════
#  VIDEO DOWNLOADER — fetch and show quality keyboard
# ═══════════════════════════════════════════════════════════════
async def _fetch_and_show_qualities(
    message,
    state,
    video_url: str,
    WARN_SIZE_BYTES: int,
    quality_state,
):
    status_msg = await message.answer("🔍 Fetching available qualities, please wait...")

    try:
        loop          = asyncio.get_running_loop()
        formats, info = await loop.run_in_executor(None, fetch_formats, video_url)
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Failed to fetch video info.</b>\n\n<code>{str(e)[:300]}</code>\n\n"
            "Make sure the URL is a valid, public video.",
            parse_mode="HTML"
        )
        await state.clear()
        return

    title      = info.get("title", "Unknown Title")
    duration   = info.get("duration", 0)
    channel    = info.get("uploader", "Unknown")
    mins, secs = divmod(duration, 60)

    await state.update_data(formats=[
        {
            "format_id": f.get("format_id"),
            "height":    f.get("height"),
            "ext":       f.get("ext"),
            "fps":       f.get("fps"),
            "filesize":  f.get("filesize") or f.get("filesize_approx"),
        }
        for f in formats
    ])
    await state.set_state(quality_state)

    await status_msg.edit_text(
        f"🎬 <b>{title}</b>\n"
        f"👤 {channel}  •  ⏱ {mins}m {secs}s\n\n"
        "Choose a download quality:\n"
        "<i>⚠️ Via link = too large for Telegram, you'll receive a gofile.io link instead.</i>",
        reply_markup=build_quality_keyboard(formats, WARN_SIZE_BYTES),
        parse_mode="HTML"
    )
