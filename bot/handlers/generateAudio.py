import asyncio
import functools
import os
from pathlib import Path
from uuid import uuid4

import numpy
import torch
import torch.serialization

from aiogram import types as aiogram_types
from aiogram.types import FSInputFile

from bark import SAMPLE_RATE, generate_audio as bark_generate_audio, preload_models
from scipy.io.wavfile import write as write_wav

# Keep track of models to avoid reloading unnecessarily, although preload_models handles this
_models_loaded = False

def _blocking_generate_audio(prompt: str, audio_path: str):
    global _models_loaded
    if not _models_loaded:
        # PyTorch 2.6 flipped weights_only=True by default, which blocks bark's
        # checkpoint loading. We explicitly allowlist the numpy type bark uses.
        torch.serialization.add_safe_globals([numpy.core.multiarray.scalar])
        # download and load all models
        preload_models()
        _models_loaded = True
        
    # generate audio from text
    audio_array = bark_generate_audio(prompt)

    # save audio to disk
    write_wav(audio_path, SAMPLE_RATE, audio_array)

async def start_audio_generation(message: aiogram_types.Message, prompt: str, STORAGE_DIR: Path):
    global _models_loaded
    
    msg_text = "🎙️ Generating your audio, please wait..."
    if not _models_loaded:
        msg_text += "\n<i>(The first time will take a few minutes to download models!)</i>"
        
    status_msg = await message.answer(msg_text, parse_mode="HTML")
    audio_path = str(STORAGE_DIR / f"{uuid4()}.wav")

    try:
        loop = asyncio.get_running_loop()
        # Run blocking model loading and inference in an executor 
        await loop.run_in_executor(
            None,
            functools.partial(_blocking_generate_audio, prompt, audio_path)
        )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Audio generation failed.</b>\n<code>{e}</code>",
            parse_mode="HTML"
        )
        return

    try:
        # Send back to telegram
        await message.answer_audio(
            audio=FSInputFile(audio_path),
            caption=f"🎙️ Audio generated for:\n<i>{prompt}</i>",
            parse_mode="HTML"
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Failed to send audio.</b>\n<code>{e}</code>",
            parse_mode="HTML"
        )
    finally:
        # Cleanup
        Path(audio_path).unlink(missing_ok=True)
