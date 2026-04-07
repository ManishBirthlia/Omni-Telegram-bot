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

os.environ["SUNO_OFFLOAD_CPU"] = "False"
os.environ["SUNO_USE_SMALL_MODELS"] = "True"

# Keep track of models to avoid reloading unnecessarily
_models_loaded = False
_device = "cuda" if torch.cuda.is_available() else "cpu"

def split_text(text, max_chars=150):
    """Split text into chunks of roughly max_chars, preferably at sentence boundaries."""
    import re
    # Split by common sentence delimiters: . ! ?
    # We use a lookbehind to keep the delimiter: (?<=[.!?])
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_chars:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If a single sentence is longer than max_chars, we have to split it anyway
            if len(sentence) > max_chars:
                # Basic split by space as fallback
                words = sentence.split(' ')
                sub_chunk = ""
                for word in words:
                    if len(sub_chunk) + len(word) <= max_chars:
                        sub_chunk += (" " if sub_chunk else "") + word
                    else:
                        chunks.append(sub_chunk)
                        sub_chunk = word
                current_chunk = sub_chunk
            else:
                current_chunk = sentence
                
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def _blocking_generate_audio(prompt: str, audio_path: str):
    global _models_loaded, _device
    
    # We use a fixed speaker for consistency across chunks
    SPEAKER = "v2/en_speaker_6"
    
    if not _models_loaded:
        print(f"Loading Bark models on: {_device.upper()}")
        
        # Monkey-patch torch.load to handle legacy Bark models in PyTorch 2.6+
        import torch
        _orig_torch_load = torch.load
        def _patched_torch_load(*args, **kwargs):
            if 'weights_only' not in kwargs:
                kwargs['weights_only'] = False
            return _orig_torch_load(*args, **kwargs)
        torch.load = _patched_torch_load

        preload_models(
            text_use_gpu=(_device == "cuda"),
            text_use_small=True,
            coarse_use_gpu=(_device == "cuda"),
            coarse_use_small=True,
            fine_use_gpu=(_device == "cuda"),
            fine_use_small=True,
            codec_use_gpu=(_device == "cuda")
        )
        _models_loaded = True
        
    # Split long text into manageable chunks for Bark (~14s each)
    chunks = split_text(prompt)
    print(f"Generating audio in {len(chunks)} chunks on {_device.upper()}...")
    
    audio_pieces = []
    for i, chunk in enumerate(chunks):
        print(f"  [Chunk {i+1}/{len(chunks)}] \"{chunk[:50]}...\"")
        # generate audio for this chunk
        audio_piece = bark_generate_audio(chunk, history_prompt=SPEAKER, silent=True)
        audio_pieces.append(audio_piece)
        
    # Merge all pieces together
    if len(audio_pieces) > 1:
        full_audio = numpy.concatenate(audio_pieces)
    else:
        full_audio = audio_pieces[0]

    # save audio to disk
    write_wav(audio_path, SAMPLE_RATE, full_audio)

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
        import html
        print(f"Bark Generation Error: {e}")
        error_text = html.escape(str(e))
        await status_msg.edit_text(
            f"❌ <b>Audio generation failed.</b>\n<code>{error_text}</code>",
            parse_mode="HTML"
        )
        return

    try:
        # Send back to telegram
        await message.answer_audio(
            audio=FSInputFile(audio_path),
            caption=f"🎙️ Audio generated for:\n<i>{prompt[:1000]}</i>",
            parse_mode="HTML"
        )
        await status_msg.delete()
    except Exception as e:
        import html
        error_text = html.escape(str(e))
        await status_msg.edit_text(
            f"❌ <b>Failed to send audio.</b>\n<code>{error_text}</code>",
            parse_mode="HTML"
        )
    finally:
        # Cleanup
        Path(audio_path).unlink(missing_ok=True)
