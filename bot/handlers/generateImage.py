import os
import base64
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from aiogram import types as aiogram_types
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

NVIDIA_API_URL = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-3-medium"
IMAGE_DIR = Path("Generated Images")
IMAGE_DIR.mkdir(exist_ok=True)

# ── Aspect-ratio choices ─────────────────────────────────────────
ASPECT_RATIOS = {
    "1:1":   "1:1  (Square)",
    "16:9":  "16:9  (Landscape Wide)",
    "9:16":  "9:16  (Portrait / Story)",
    "4:3":   "4:3  (Classic Landscape)",
    "3:4":   "3:4  (Classic Portrait)",
    "21:9":  "21:9  (Ultra-Wide)",
}

# ── Quality presets ──────────────────────────────────────────────
QUALITY_PRESETS = {
    "low": {
        "label": "⚡ Low  (Fast, 20 steps)",
        "steps": 20,
        "cfg_scale": 4,
    },
    "balanced": {
        "label": "⚖️ Balanced  (35 steps)",
        "steps": 35,
        "cfg_scale": 5,
    },
    "high": {
        "label": "🔥 High  (50 steps, best detail)",
        "steps": 50,
        "cfg_scale": 7,
    },
}


# ── Keyboard builders ────────────────────────────────────────────
def build_aspect_ratio_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"img_ar:{key}")]
        for key, label in ASPECT_RATIOS.items()
    ]
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="img_ar:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_img_quality_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=q["label"], callback_data=f"img_quality:{key}")]
        for key, q in QUALITY_PRESETS.items()
    ]
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="img_quality:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_neg_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Skip (no negative prompt)", callback_data="img_neg:skip")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="img_neg:cancel")],
    ])


# ── Main generation function ────────────────────────────────────
async def generate_image(
    message: aiogram_types.Message,
    prompt: str,
    aspect_ratio: str = "16:9",
    quality_key: str = "balanced",
    negative_prompt: str = "",
):
    """Generate an image via NVIDIA Stable Diffusion API, save locally, and send to the user."""

    quality = QUALITY_PRESETS.get(quality_key, QUALITY_PRESETS["balanced"])
    ar_label = ASPECT_RATIOS.get(aspect_ratio, aspect_ratio)

    status_msg = await message.answer(
        "🎨 <b>Generating your image...</b>\n\n"
        f"<b>Aspect Ratio:</b> {ar_label}\n"
        f"<b>Quality:</b> {quality['label']}\n"
        f"<b>Prompt:</b> <code>{prompt[:150]}</code>\n"
        + (f"<b>Negative:</b> <code>{negative_prompt[:100]}</code>\n" if negative_prompt else "")
        + "\n⏳ This may take a moment...",
        parse_mode="HTML",
    )

    headers = {
        "Authorization": f"Bearer {os.getenv('NVIDIA_API_KEY')}",
        "Accept": "application/json",
    }

    payload = {
        "prompt": prompt,
        "cfg_scale": quality["cfg_scale"],
        "aspect_ratio": aspect_ratio,
        "seed": 0,
        "steps": quality["steps"],
        "negative_prompt": negative_prompt,
    }

    try:
        response = requests.post(NVIDIA_API_URL, headers=headers, json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()

        # Extract base64 image (different API response formats)
        image_b64 = None
        if "image" in data:
            image_b64 = data["image"]
        elif "artifacts" in data and len(data["artifacts"]) > 0:
            image_b64 = data["artifacts"][0].get("base64")

        if not image_b64:
            await status_msg.edit_text(
                "❌ <b>Image generation failed.</b>\nNo image data returned by the API.",
                parse_mode="HTML",
            )
            return

        # Decode and save
        image_bytes = base64.b64decode(image_b64)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in " _-" else "" for c in prompt[:50]).strip()
        filename = f"{timestamp}_{safe_name}.png"
        filepath = IMAGE_DIR / filename
        filepath.write_bytes(image_bytes)

        # Send the image to the user
        await status_msg.edit_text("📤 <b>Uploading image to Telegram...</b>", parse_mode="HTML")

        await message.answer_photo(
            photo=FSInputFile(filepath),
            caption=(
                f"🖼️ <b>Image Generated!</b>\n\n"
                f"<b>Aspect Ratio:</b> {ar_label}\n"
                f"<b>Quality:</b> {quality_key.capitalize()}\n"
                f"<b>Prompt:</b> <i>{prompt[:150]}</i>\n"
                + (f"<b>Negative:</b> <i>{negative_prompt[:80]}</i>\n" if negative_prompt else "")
                + f"\n📁 Saved to: <code>Generated Images/{filename}</code>"
            ),
            parse_mode="HTML",
        )
        await status_msg.delete()
        # Uncomment the line below to delete local files after delivery:
        filepath.unlink(missing_ok=True)

    except requests.exceptions.Timeout:
        await status_msg.edit_text(
            "❌ <b>Request timed out.</b>\nThe API took too long to respond. Please try again.",
            parse_mode="HTML",
        )
    except requests.exceptions.HTTPError as e:
        await status_msg.edit_text(
            f"❌ <b>API error.</b>\n<code>{str(e)[:300]}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Image generation failed.</b>\n<code>{str(e)[:300]}</code>",
            parse_mode="HTML",
        )
