
#  CANCEL IF COMMAND
async def cancel_if_command(
    message: aiogram_types.Message,
    state: FSMContext,
    resume_command: str = "/start"
) -> bool:
    if message.text and message.text.startswith("/"):
        await state.clear()
        await message.answer(
            f"⚠️ Flow cancelled — you sent a command.\n"
            f"Use <code>{resume_command}</code> to start again.",
            parse_mode="HTML"
        )
        return True
    return False

# ═══════════════════════════════════════════════════════════════
#  GOFILE.IO UPLOAD
#
#  Called only when downloaded file exceeds TELEGRAM_MAX_BYTES.
#  Two-step process:
#    1. GET  api.gofile.io/servers       → pick best upload server
#    2. POST {server}.gofile.io/uploadFile → upload, get public link
#
#  Blocking — always called via run_in_executor.
#  Files expire after 10 days of no downloads (free tier).
# ═══════════════════════════════════════════════════════════════
def _upload_to_gofile(filepath: Path) -> str:
    # Step 1 — find the best server
    server_resp = requests.get("https://api.gofile.io/servers", timeout=15)
    server_resp.raise_for_status()
    servers = server_resp.json().get("data", {}).get("servers", [])
    if not servers:
        raise RuntimeError("gofile.io returned no available servers.")
    server_name = servers[0]["name"]

    # Step 2 — upload the file
    upload_url = f"https://{server_name}.gofile.io/uploadFile"
    with open(filepath, "rb") as f:
        upload_resp = requests.post(
            upload_url,
            files={"file": (filepath.name, f)},
            timeout=300   # generous timeout for large files
        )
    upload_resp.raise_for_status()
    data = upload_resp.json()

    if data.get("status") != "ok":
        raise RuntimeError(f"gofile.io upload failed: {data}")

    return data["data"]["downloadPage"]


async def upload_to_gofile_async(filepath: Path) -> str:
    """Async wrapper — runs _upload_to_gofile in a thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _upload_to_gofile, filepath)
