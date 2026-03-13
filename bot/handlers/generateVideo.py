import asyncio
import functools
import os
from pathlib import Path
from uuid import uuid4

import requests
from aiogram import types as aiogram_types
from aiogram.types import FSInputFile

# ═══════════════════════════════════════════════════════════════
#  VIDEO GENERATION  (LTX API)
# ═══════════════════════════════════════════════════════════════
def _blocking_generate_video(prompt: str, video_path: str, LTX_API_URL: str):
    payload = {
        "prompt":     prompt,
        "model":      "ltx-2-pro",
        "duration":   8,
        "resolution": "1920x1080",
    }
    headers = {
        "Authorization": f"Bearer {os.getenv('LTX_2_PRO_API_KEY')}",
        "Content-Type":  "application/json",
    }
    response = requests.post(LTX_API_URL, json=payload, headers=headers)
    response.raise_for_status()
    with open(video_path, "wb") as f:
        f.write(response.content)


async def start_video_generation(message: aiogram_types.Message, prompt: str, STORAGE_DIR: Path, LTX_API_URL: str):
    status_msg = await message.answer("🎬 Generating your video, please wait...")
    video_path = str(STORAGE_DIR / f"{uuid4()}.mp4")

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            functools.partial(_blocking_generate_video, prompt, video_path, LTX_API_URL)
        )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Video generation failed.</b>\n<code>{e}</code>",
            parse_mode="HTML"
        )
        return

    try:
        await message.answer_video(
            video=FSInputFile(video_path),
            caption=f"🎬 Video generated for:\n<i>{prompt}</i>",
            parse_mode="HTML"
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Failed to send video.</b>\n<code>{e}</code>",
            parse_mode="HTML"
        )
    finally:
        Path(video_path).unlink(missing_ok=True)
