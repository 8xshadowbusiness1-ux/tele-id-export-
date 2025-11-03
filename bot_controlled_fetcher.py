"""
bot_controlled_fetcher.py
Full script: bot-controlled OTP / 2FA / fetch members / progress + ~15 commands.
"""

import time, json, os, csv, requests, traceback
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
# ----------------------------- DEFAULTS -----------------------------
DEFAULT_API_ID = 18085901
DEFAULT_API_HASH = "baa5a6ca152c717e88ea45f888d3af74"
DEFAULT_PHONE = "+918436452250"
DEFAULT_BOT_TOKEN = "8254353086:AAEMim12HX44q0XYaFWpbB3J7cxm4VWprEc"
DEFAULT_USER_CHAT_ID = 1602198875
DEFAULT_TUTORIAL_ID = -1002647054427
OUTPUT_CSV = "tutorial_members.csv"
STATE_FILE = "state.json"
PROGRESS_BATCH = 500
GETUPDATES_TIMEOUT = 10
# --------------------------------------------------------------------

# --------------------------- BOT API HELPERS ------------------------
def bot_send(bot_token, chat_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        print("bot_send error:", e)

def bot_send_file(bot_token, chat_id, file_path, caption=None):
    try:
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendDocument",
                data=data,
                files=files,
                timeout=120,
            )
    except Exception as e:
        print("bot_send_file error:", e)

def bot_get_updates(bot_token, offset=None, timeout=GETUPDATES_TIMEOUT):
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=timeout + 5)
        return r.json()
    except Exception:
        return {"ok": False, "result": []}

# --------------------------- STATE HELPERS --------------------------
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, "r", encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_state(s):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("save_state error:", e)

# --------------------------- TELETHON FIXES --------------------------

# --- Fix 1: send_code_request returns a hash, store it ---
def tele_send_code(api_id, api_hash, phone, session_name="session_bot"):
    """Sends code request and saves phone_code_hash."""
    try:
        async def _inner():
            client = TelegramClient(session_name, api_id, api_hash)
            await client.connect()
            result = await client.send_code_request(phone)
            await client.disconnect()
            return result.phone_code_hash
        import asyncio
        phone_code_hash = asyncio.run(_inner())
        state = load_state()
        state["phone_code_hash"] = phone_code_hash
        save_state(state)
        return True, "Code request sent."
    except Exception as e:
        return False, f"send_code error: {e}"

# --- Fix 2: use stored phone_code_hash when signing in ---
def tele_sign_in_with_code(api_id, api_hash, phone, code, session_name="session_bot"):
    """Try sign in with phone + code + stored hash."""
    try:
        async def _inner():
            client = TelegramClient(session_name, api_id, api_hash)
            await client.connect()
            state = load_state()
            phone_code_hash = state.get("phone_code_hash")
            if not phone_code_hash:
                await client.disconnect()
                return (False, False, "Missing phone_code_hash (you must /login again).")
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                await client.disconnect()
                return (True, False, "Signed in successfully.")
            except SessionPasswordNeededError:
                await client.disconnect()
                return (True, True, "2FA required.")
        import asyncio
        ok, needs_2fa, msg = asyncio.run(_inner())
        return ok, needs_2fa, msg
    except Exception as e:
        return False, False, f"sign_in_code error: {e}"

# --- 2FA ---
def tele_sign_in_with_password(api_id, api_hash, password, session_name="session_bot"):
    try:
        async def _inner():
            client = TelegramClient(session_name, api_id, api_hash)
            await client.connect()
            try:
                await client.sign_in(password=password)
                await client.disconnect()
                return (True, "2FA sign-in successful.")
            except Exception as e:
                await client.disconnect()
                return (False, f"2FA sign-in failed: {e}")
        import asyncio
        ok, msg = asyncio.run(_inner())
        return ok, msg
    except Exception as e:
        return False, f"2FA wrapper error: {e}"

# --- Member Fetch ---
def tele_fetch_members(api_id, api_hash, tutorial_group, progress_callback=None, session_name="session_bot"):
    members = []
    try:
        async def _inner():
            client = TelegramClient(session_name, api_id, api_hash)
            await client.connect()
            processed = 0
            try:
                async for user in client.iter_participants(tutorial_group, aggressive=True):
                    members.append((
                        user.id,
                        getattr(user, "username", "") or "",
                        getattr(user, "first_name", "") or "",
                        getattr(user, "last_name", "") or "",
                        getattr(user, "phone", "") or "",
                    ))
                    processed_local = len(members)
                    if progress_callback and processed_local % PROGRESS_BATCH == 0:
                        progress_callback(processed_local)
                await client.disconnect()
                return True, "Fetch complete."
            except FloodWaitError as fw:
                await client.disconnect()
                return False, f"FloodWait: {fw.seconds}"
            except RpcError as re:
                await client.disconnect()
                return False, f"RPC error: {re}"
        import asyncio
        ok, msg = asyncio.run(_inner())
        return ok, msg, members
    except Exception as e:
        return False, f"fetch wrapper error: {e}", members

# --------------------------- COMMAND HANDLER --------------------------
def process_command(cmd_text, from_chat_id, config):
    state = load_state()
    bot_token = config["bot_token"]
    api_id = config["api_id"]
    api_hash = config["api_hash"]
    phone = config["phone"]
    tutorial_group = config["tutorial_id"]

    def reply(text):
        print(f"Reply to {from_chat_id}: {text}")
        bot_send(bot_token, from_chat_id, text)

    text = cmd_text.strip()
    lower = text.lower()

    if lower.startswith("/hello") or lower.startswith("/start"):
        reply("Hello Vishal! Main ready hoon 😎\nCommands ke liye /help likho.")
        return

    if lower.startswith("/help"):
        reply(
            "Commands:\n"
            "/login - Send OTP\n"
            "/otp <code> - Verify OTP\n"
            "/2fa <password> - 2FA login\n"
            "/fetch - Fetch tutorial members\n"
            "/users_count - Show how many fetched\n"
            "/sendfile - Send last CSV\n"
            "/status - Show current state\n"
            "/stop - Stop fetching\n"
            "/ping - Check bot\n"
        )
        return

    if lower.startswith("/ping"):
        reply("💓 Pong! Time: " + time.strftime("%Y-%m-%d %H:%M:%S"))
        return

    if lower.startswith("/login"):
        ok, msg = tele_send_code(api_id, api_hash, phone)
        if ok:
            state["awaiting_otp"] = True
            state["awaiting_2fa"] = False
            save_state(state)
            reply("📱 OTP bhej diya! Jab code aaye to /otp <code> likho.")
        else:
            reply("OTP request failed: " + msg)
        return

    if lower.startswith("/otp") or (state.get("awaiting_otp") and text.isdigit()):
        parts = text.split()
        code = parts[1] if len(parts) > 1 and parts[0].lower() == "/otp" else parts[0]
        reply("🔐 Verifying OTP...")
        ok, needs_2fa, msg = tele_sign_in_with_code(api_id, api_hash, phone, code)
        if not ok:
            reply("❌ Sign-in failed: " + msg)
            return
        if needs_2fa:
            state["awaiting_2fa"] = True
            save_state(state)
            reply("⚠️ 2FA required. Use /2fa <password>.")
        else:
            state["logged_in"] = True
            save_state(state)
            reply("✅ Login successful! Now you can /fetch members.")
        return

    if lower.startswith("/2fa") or (state.get("awaiting_2fa") and len(text) > 0):
        parts = text.split(maxsplit=1)
        pwd = parts[1] if parts[0].lower() == "/2fa" and len(parts) > 1 else text
        reply("🔐 Trying 2FA...")
        ok, msg = tele_sign_in_with_password(api_id, api_hash, pwd)
        if ok:
            state["logged_in"] = True
            save_state(state)
            reply("✅ 2FA success. You can /fetch members now.")
        else:
            reply("❌ 2FA failed: " + msg)
        return

    if lower.startswith("/fetch"):
        if not state.get("logged_in"):
            reply("⚠️ Not logged in. Use /login first.")
            return

        state["fetching"] = True
        save_state(state)
        reply("🚀 Fetching members...")

        def progress_cb(c):
            reply(f"📊 Processed {c} members so far...")

        ok, msg, members = tele_fetch_members(api_id, api_hash, tutorial_group, progress_callback=progress_cb)
        if not ok:
            reply("❌ Fetch failed: " + msg)
            state["fetching"] = False
            save_state(state)
            return

        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["user_id", "username", "first_name", "last_name", "phone"])
            for m in members:
                w.writerow(m)

        bot_send_file(bot_token, from_chat_id, OUTPUT_CSV, "Tutorial Members CSV")
        reply(f"✅ Fetch done! Total {len(members)} members.")
        state["fetching"] = False
        save_state(state)
        return

    if lower.startswith("/users_count"):
        if os.path.exists(OUTPUT_CSV):
            cnt = sum(1 for _ in open(OUTPUT_CSV, "r", encoding="utf-8")) - 1
            reply(f"📄 Total {cnt} users in CSV.")
        else:
            reply("No CSV yet.")
        return

    if lower.startswith("/status"):
        reply("📊 Current state:\n" + json.dumps(load_state(), indent=2))
        return

    reply("❓ Unknown command. Type /help.")

# ---------------------------- MAIN LOOP ----------------------------
def main_loop():
    print("=== Bot-controlled fetcher starting ===")
    config = {
        "api_id": DEFAULT_API_ID,
        "api_hash": DEFAULT_API_HASH,
        "phone": DEFAULT_PHONE,
        "bot_token": DEFAULT_BOT_TOKEN,
        "user_chat_id": DEFAULT_USER_CHAT_ID,
        "tutorial_id": DEFAULT_TUTORIAL_ID,
    }

    offset = None
    print("Polling Telegram updates...")

    while True:
        try:
            data = bot_get_updates(config["bot_token"], offset=offset)
            if not data.get("ok"):
                time.sleep(1)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")
                print(f"From {chat_id}: {text}")
                if str(chat_id) != str(config["user_chat_id"]):
                    bot_send(config["bot_token"], chat_id, "🚫 Private bot. Unauthorized access.")
                    continue
                process_command(text, chat_id, config)
            time.sleep(1)
        except KeyboardInterrupt:
            print("🛑 Exiting.")
            break
        except Exception as e:
            print("Main loop error:", e)
            time.sleep(2)

if __name__ == "__main__":
    main_loop()
