import os
import asyncio
import html
from pathlib import Path
from aiogram import types as aiogram_types
from aiogram.types import FSInputFile

async def transcribe_audio(file_path, whisper_client):
    """Transcribe audio file using Whisper"""
    try:
        # Local whisper.transcribe is synchronous and expects a string path or ndarray.
        # We run it in a thread to avoid blocking the event loop.
        result = await asyncio.to_thread(
            whisper_client.transcribe,
            str(file_path),
            task="translate",
            language="en"
        )
        
        if isinstance(result, dict) and 'text' in result:
            return result['text']
        return str(result)
    except Exception as e:
        print(f"Transcription error: {e}")
        return None

async def summarize_text(text, nvidia_chat_client_1):
    """Summarize text using NVIDIA AI."""
    if not text or len(text.strip()) < 10:
        return "Transcription is too short to summarize."
        
    try:
        prompt = f"Please provide a concise bullet-point summary of the following transcription:\n\n{text}"
        completion = await asyncio.to_thread(
            nvidia_chat_client_1.chat.completions.create,
            model="nvidia/nemotron-3-nano-30b-a3b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Summarization error: {e}")
        return "Could not generate summary."

async def process_transcription(message: aiogram_types.Message, file_id: str, bot, whisper_client, nvidia_chat_client_1):
    """Download file, transcribe, summarize, and send results."""
    status_msg = await message.answer("⏳ <b>Downloading audio...</b>", parse_mode="HTML")
    
    # Create temp directory if not exists
    temp_dir = Path("temp_transcriptions")
    temp_dir.mkdir(exist_ok=True)
    
    file_info = await bot.get_file(file_id)
    file_path = temp_dir / Path(file_info.file_path).name
    
    try:
        await bot.download_file(file_info.file_path, destination=file_path)
        
        await status_msg.edit_text("🎙️ <b>Transcribing with Whisper...</b>", parse_mode="HTML")
        transcript = await transcribe_audio(file_path, whisper_client)
        
        if not transcript or not transcript.strip():
            await status_msg.edit_text("❌ <b>Transcription failed or audio is empty.</b>", parse_mode="HTML")
            return

        # await status_msg.edit_text("📝 <b>Generating summary...</b>", parse_mode="HTML")
        # summary = await summarize_text(transcript, nvidia_chat_client_1)
        
        # Send transcript (if long, send as file)
        if len(transcript) > 4000:
            transcript_file = temp_dir / f"transcript_{file_id}.txt"
            with open(transcript_file, "w", encoding="utf-8") as f:
                f.write(transcript)
            await message.answer_document(
                FSInputFile(transcript_file), 
                caption="📄 <b>Full Transcription</b> (File is too long for a message)",
                parse_mode="HTML"
            )
            transcript_file.unlink(missing_ok=True)
        else:
            # Escape HTML to prevent parsing errors
            safe_transcript = html.escape(transcript)
            await message.answer(f"📄 <b>Transcription:</b>\n\n{safe_transcript}", parse_mode="HTML")
            
        # await message.answer(f"💡 <b>Summary:</b>\n\n{summary}", parse_mode="HTML")
        await status_msg.delete()
        
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Error:</b> <code>{str(e)}</code>", parse_mode="HTML")
    finally:
        if file_path.exists():
            file_path.unlink()
