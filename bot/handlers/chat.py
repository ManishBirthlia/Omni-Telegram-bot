import re
import html
from aiogram import types as aiogram_types


def markdown_to_telegram_html(text: str) -> str:
    """Convert LLM Markdown output → Telegram-safe HTML.

    Handles: code blocks, inline code, bold, italic, strikethrough,
    headings, bullet/numbered lists, blockquotes, and horizontal rules.
    Unsupported / model-invented tags (e.g. <think>, <br>) are stripped.
    """

    # 1. Strip model-invented tags (<think>…</think>, <br>, etc.)
    text = re.sub(r"</?(?:think|br|hr|div|span|p)\s*/?>", "", text, flags=re.IGNORECASE)

    # 2. Escape HTML-special chars so raw angle brackets don't break parsing
    #    BUT first protect fenced code blocks (we'll restore them later).
    code_blocks: list[str] = []

    def _stash_code_block(m: re.Match) -> str:
        lang = m.group(1) or ""
        code = html.escape(m.group(2))
        code_blocks.append(f"<pre><code>{code}</code></pre>" if not lang
                           else f"<pre><code class=\"language-{lang}\">{code}</code></pre>")
        return f"\x00CODEBLOCK{len(code_blocks) - 1}\x00"

    text = re.sub(r"```(\w*)\n(.*?)```", _stash_code_block, text, flags=re.DOTALL)

    # 3. Escape remaining HTML entities
    text = html.escape(text)

    # 4. Inline code  `…`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # 5. Bold  **…** or __…__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # 6. Italic  *…* or _…_  (but not inside words like some_var)
    text = re.sub(r"(?<!\w)\*([^*]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"<i>\1</i>", text)

    # 7. Strikethrough  ~~…~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # 8. Headings  ### Text  →  bold line
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # 9. Blockquotes  > text
    text = re.sub(r"^&gt;\s?(.+)$", r"<blockquote>\1</blockquote>", text, flags=re.MULTILINE)

    # 10. Bullet lists  - item  or  * item  →  • item
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)

    # 11. Numbered lists  1. item  (keep as-is, just tidy indent)
    text = re.sub(r"^\s*(\d+)\.\s+", r"\1. ", text, flags=re.MULTILINE)

    # 12. Horizontal rules  --- or ***  →  thin line
    text = re.sub(r"^[-*_]{3,}\s*$", "───────────────", text, flags=re.MULTILINE)

    # 13. Restore stashed code blocks
    for i, block in enumerate(code_blocks):
        text = text.replace(f"\x00CODEBLOCK{i}\x00", block)

    # 14. Collapse 3+ blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


async def _send_formatted(message: aiogram_types.Message, text: str):
    """Send text as Telegram HTML; fall back to plain text on parse error."""
    for i in range(0, len(text), 4096):
        chunk = text[i:i + 4096]
        try:
            await message.answer(chunk, parse_mode="HTML")
        except Exception:
            # If HTML parsing fails, send as plain text
            await message.answer(chunk)


async def groq_AI_chatting(message: aiogram_types.Message, SYSTEM_INSTRUCTION, client):
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user",   "content": message.text},
            ],
            model="llama-3.3-70b-versatile",
        )
        formatted = markdown_to_telegram_html(response.choices[0].message.content)
        await _send_formatted(message, formatted)
    except Exception as e:
        print(f"Groq error: {e}")
        await message.answer("Sorry, I had trouble processing that. Could you try again?")


async def nvidia_AI_chatting(message: aiogram_types.Message, SYSTEM_INSTRUCTION, nvidia_chat_client_1):
    try:
        completion = nvidia_chat_client_1.chat.completions.create(
            model="nvidia/nemotron-3-nano-30b-a3b",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user",   "content": message.text},
            ],
            temperature=1,
            top_p=1,
            max_tokens=16384,
            extra_body={"reasoning_budget": 16384, "chat_template_kwargs": {"enable_thinking": True}},
            stream=True,
        )

        full_response = ""
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                full_response += delta.content

        if full_response.strip():
            formatted = markdown_to_telegram_html(full_response)
            await _send_formatted(message, formatted)
        else:
            await message.answer("I couldn't generate a response. Please try again.")

    except Exception as e:
        print(f"NVIDIA AI error: {e}")
        await message.answer("Sorry, I had trouble processing that. Could you try again?")

async def deepseek_AI_chatting(message: aiogram_types.Message, SYSTEM_INSTRUCTION, nvidia_chat_client_2):
    try:
        completion = nvidia_chat_client_2.chat.completions.create(
            model="deepseek-ai/deepseek-v3.2",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user",   "content": message.text},
            ],
            temperature=1,
            top_p=0.95,
            max_tokens=16384,
            extra_body={"chat_template_kwargs": {"thinking": True}},
            stream=True,
        )

        full_response = ""
        reasoning_response = ""
        
        for chunk in completion:
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                reasoning_response += reasoning
                
            if delta.content is not None:
                full_response += delta.content

        final_text = ""
        if reasoning_response.strip():
            reasoning_lines = reasoning_response.strip().split('\n')
            reasoning_block = "\n".join([f"> {line}" for line in reasoning_lines])
            final_text += f"> 🤔 **Thinking:**\n{reasoning_block}\n\n"
        
        final_text += full_response

        if final_text.strip():
            formatted = markdown_to_telegram_html(final_text)
            await _send_formatted(message, formatted)
        else:
            await message.answer("I couldn't generate a response. Please try again.")

    except Exception as e:
        print(f"DeepSeek AI error: {e}")
        await message.answer("Sorry, I had trouble processing that. Could you try again?")