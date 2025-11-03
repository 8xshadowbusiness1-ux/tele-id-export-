"""
bot_controlled_fetcher.py
Full script: bot-controlled OTP / 2FA / fetch members / progress + ~15 commands.

WARNING: Defaults in this file are EXAMPLE values (you provided). Do NOT publish real secrets.
Run locally on trusted machine for security.
"""

import time, json, os, csv, requests, traceback
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError

# ----------------------------- DEFAULTS (EXAMPLES) -----------------------------
DEFAULT_API_ID = 18085901
DEFAULT_API_HASH = "baa5a6ca152c717e88ea45f888d3af74"
DEFAULT_PHONE = "+918436452250"
DEFAULT_BOT_TOKEN = "8254353086:AAEMim12HX44q0XYaFWpbB3J7cxm4VWprEc"
DEFAULT_USER_CHAT_ID = 1602198875  # your chat id where bot messages are expected
DEFAULT_TUTORIAL_ID = -1002647054427
OUTPUT_CSV = "tutorial_members.csv"
STATE_FILE = "state.json"
PROGRESS_BATCH = 500
GETUPDATES_TIMEOUT = 10
# -------------------------------------------------------------------------------

# --------------------------- Bot API helper functions ---------------------------
def bot_send(bot_token, chat_id, text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)
        return r.ok
    except Exception as e:
        print("bot_send error:", e)
        return False

def bot_send_file(bot_token, chat_id, file_path, caption=None):
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            r = requests.post(url, data=data, files=files, timeout=120)
        return r.ok
    except Exception as e:
        print("bot_send_file error:", e)
        return False

def bot_get_updates(bot_token, offset=None, timeout=GETUPDATES_TIMEOUT):
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=timeout + 5)
        return r.json()
    except Exception as e:
        print("bot_get_updates error:", e)
        return {"ok": False, "result": []}

# ------------------------------- State helpers --------------------------------
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

# ------------------------ Telethon action wrappers (sync) ----------------------
# We'll create short-lived Telethon clients per action so script stays simple.
def tele_send_code(api_id, api_hash, phone, session_name="session_bot"):
    """Sends code request, returns True/False and message."""
    try:
        async def _inner():
            client = TelegramClient(session_name, api_id, api_hash)
            await client.connect()
            await client.send_code_request(phone)
            await client.disconnect()
        import asyncio; asyncio.run(_inner())
        return True, "Code request sent."
    except Exception as e:
        return False, f"send_code error: {e}"

def tele_sign_in_with_code(api_id, api_hash, phone, code, session_name="session_bot"):
    """Try sign in with code. Return (ok, needs_2fa(bool), message)."""
    try:
        async def _inner():
            client = TelegramClient(session_name, api_id, api_hash)
            await client.connect()
            try:
                await client.sign_in(phone, code)
                await client.disconnect()
                return (True, False, "Signed in without 2FA.")
            except SessionPasswordNeededError:
                await client.disconnect()
                return (True, True, "2FA required.")
        import asyncio
        ok, needs_2fa, msg = asyncio.run(_inner())
        return ok, needs_2fa, msg
    except Exception as e:
        return False, False, f"sign_in_code error: {e}"

def tele_sign_in_with_password(api_id, api_hash, password, session_name="session_bot"):
    """Complete 2FA sign-in using stored session - Telethon will pick existing session."""
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

def tele_fetch_members(api_id, api_hash, tutorial_group, progress_callback=None, session_name="session_bot"):
    """
    Fetch all members from tutorial_group.
    progress_callback(processed_count) will be called periodically.
    Returns (ok, message, members_list)
    """
    members = []
    try:
        async def _inner():
            client = TelegramClient(session_name, api_id, api_hash)
            await client.connect()
            processed = 0
            try:
                async for user in client.iter_participants(tutorial_group, aggressive=True):
                    processed_nonlocal_append = (user.id, getattr(user, "username", "") or "", getattr(user, "first_name", "") or "", getattr(user, "last_name", "") or "", getattr(user, "phone", "") or "")
                    members.append(processed_nonlocal_append)
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

# ----------------------------- Command handling --------------------------------
def process_command(cmd_text, from_chat_id, config):
    """Main command router. cmd_text is raw text from user."""
    state = load_state()
    bot_token = config["bot_token"]
    api_id = config["api_id"]
    api_hash = config["api_hash"]
    phone = config["phone"]
    tutorial_group = config["tutorial_id"]

    # helper to send and log
    def reply(text):
        print(f"Reply to {from_chat_id}: {text}")
        bot_send(bot_token, from_chat_id, text)

    text = cmd_text.strip()
    lower = text.lower()

    # Basic commands
    if lower.startswith("/hello") or lower.startswith("/start"):
        reply("Hello! Main ready hoon. Commands ke liye /help type karo.")
        return

    if lower.startswith("/help"):
        reply(
            "Commands:\n"
            "/login - Trigger OTP request\n"
            "/otp <code> or just send code - Verify OTP\n"
            "/2fa <password> or just send password - Send 2-step password\n"
            "/fetch - Start fetching tutorial members\n"
            "/pause - Pause current fetch (if running)\n"
            "/resume - Resume fetch (not implemented fancy; restart)\n"
            "/status - Show current state\n"
            "/sendfile - Re-send last CSV\n"
            "/users_count - Show how many fetched so far\n"
            "/stop - Stop any running fetch\n"
            "/ping - ping\n"
            "/cancel - cancel waiting for otp/2fa\n"
            "/restart - restart script (manual)\n"
            "/help - show this"
        )
        return

    if lower.startswith("/ping"):
        reply("Pong! Time: " + time.strftime("%Y-%m-%d %H:%M:%S"))
        return

    # /login: trigger code request
    if lower.startswith("/login"):
        ok, msg = tele_send_code(api_id, api_hash, phone)
        if ok:
            state["awaiting_otp"] = True
            state["awaiting_2fa"] = False
            save_state(state)
            reply("OTP request bhej diya. Jab code aaye to is chat me /otp <code> ya sirf <code> bhej do.")
        else:
            reply("OTP request failed: " + msg)
        return

    # /otp handling: either "/otp 12345" or just "12345"
    if lower.startswith("/otp") or (state.get("awaiting_otp") and text.isdigit()):
        parts = text.split()
        code = parts[1] if len(parts) > 1 and parts[0].lower() == "/otp" else (parts[0] if parts[0].isdigit() else None)
        if not code:
            reply("OTP format invalid. Use /otp 12345 or paste only the digits.")
            return
        reply("OTP mila. Trying to sign in...")
        ok, needs_2fa, msg = tele_sign_in_with_code(api_id, api_hash, phone, code)
        if not ok:
            reply("Sign-in failed: " + msg)
            state.pop("awaiting_otp", None)
            save_state(state)
            return
        if needs_2fa:
            state["awaiting_2fa"] = True
            state.pop("awaiting_otp", None)
            save_state(state)
            reply("Account needs 2FA. Send /2fa <password> or just paste your password in chat.")
            return
        # success
        state["logged_in"] = True
        state.pop("awaiting_otp", None)
        state.pop("awaiting_2fa", None)
        save_state(state)
        reply("Login successful. You can now /fetch members.")
        return

    # /2fa handling: either "/2fa pass" or direct text when awaiting_2fa
    if lower.startswith("/2fa") or (state.get("awaiting_2fa") and len(text) > 0):
        parts = text.split(maxsplit=1)
        pwd = parts[1] if parts[0].lower() == "/2fa" and len(parts) > 1 else (text if state.get("awaiting_2fa") else None)
        if not pwd:
            reply("2FA password missing. Use /2fa <password> or paste password.")
            return
        reply("Trying 2FA sign-in...")
        ok, msg = tele_sign_in_with_password(api_id, api_hash, pwd)
        if ok:
            state["logged_in"] = True
            state.pop("awaiting_2fa", None)
            save_state(state)
            reply("2FA success. You can /fetch members now.")
        else:
            reply("2FA failed: " + msg)
        return

    # /fetch: start fetching members (runs blocking until done)
    if lower.startswith("/fetch"):
        if not state.get("logged_in"):
            reply("Not logged in yet. Use /login first.")
            return

        # set running flag
        state["fetching"] = True
        save_state(state)
        reply("Fetch starting... I will send progress messages every {} members.".format(PROGRESS_BATCH))

        def progress_cb(processed_count):
            reply(f"Processed {processed_count} members so far...")

        ok, msg, members = tele_fetch_members(api_id, api_hash, tutorial_group, progress_callback=progress_cb)
        if not ok:
            reply("Fetch failed: " + msg)
            state.pop("fetching", None)
            save_state(state)
            return

        # Save CSV
        try:
            with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["user_id", "username", "first_name", "last_name", "phone"])
                for (uid, uname, fname, lname, phonev) in members:
                    w.writerow([uid, uname, fname, lname, phonev])
            reply(f"Fetch done. Total: {len(members)}. Sending CSV...")
            sent = bot_send_file(bot_token, from_chat_id, OUTPUT_CSV, caption="Tutorial members CSV")
            if sent:
                reply("CSV sent successfully.")
            else:
                reply("CSV send failed. Check logs.")
        except Exception as e:
            reply("Error saving/sending CSV: " + str(e))
        state.pop("fetching", None)
        save_state(state)
        return

    # /users_count - show how many fetched so far (if CSV exists)
    if lower.startswith("/users_count"):
        if os.path.exists(OUTPUT_CSV):
            try:
                with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
                    cnt = sum(1 for _ in f) - 1
                reply(f"CSV exists. Rows (excluding header): {cnt}")
            except Exception as e:
                reply("Error reading CSV: " + str(e))
        else:
            reply("No CSV found yet.")
        return

    if lower.startswith("/sendfile"):
        if os.path.exists(OUTPUT_CSV):
            ok = bot_send_file(bot_token, from_chat_id, OUTPUT_CSV, caption="Requested CSV")
            if ok:
                reply("CSV re-sent.")
            else:
                reply("CSV send failed.")
        else:
            reply("No CSV to send.")
        return

    if lower.startswith("/pause"):
        # simple implementation: set fetching flag false (won't interrupt running tele_fetch since it's blocking)
        reply("Pause requested. Note: if a fetch is already running it may not stop immediately.")
        state["pause_requested"] = True
        save_state(state)
        return

    if lower.startswith("/resume"):
        reply("Resume: re-run /fetch to restart fetching (resume not fully automatic in this simple script).")
        return

    if lower.startswith("/stop"):
        # set a stop flag - tele_fetch in this simple script won't check frequently; we notify user.
        state["stop_requested"] = True
        save_state(state)
        reply("Stop requested. If a fetch is running, it may still finish the current batch.")
        return

    if lower.startswith("/status"):
        st = load_state()
        reply("Current state: " + json.dumps(st, indent=2))
        return

    if lower.startswith("/cancel"):
        state.pop("awaiting_otp", None)
        state.pop("awaiting_2fa", None)
        save_state(state)
        reply("Cancelled waiting for OTP/2FA.")
        return

    if lower.startswith("/restart"):
        reply("You asked to restart the script. Please manually restart the process.")
        return

    # Unknown command: treat as potential OTP or 2FA if awaiting
    if state.get("awaiting_otp") and text.isdigit():
        process_command("/otp " + text, from_chat_id, config)
        return
    if state.get("awaiting_2fa"):
        process_command("/2fa " + text, from_chat_id, config)
        return

    reply("Unknown command or text. Type /help for command list.")


# ---------------------------- Main polling loop --------------------------------
def main_loop():
    print("=== Bot-controlled fetcher starting ===")
    # Load config or use defaults
    config = {
        "api_id": DEFAULT_API_ID,
        "api_hash": DEFAULT_API_HASH,
        "phone": DEFAULT_PHONE,
        "bot_token": DEFAULT_BOT_TOKEN,
        "user_chat_id": DEFAULT_USER_CHAT_ID,
        "tutorial_id": DEFAULT_TUTORIAL_ID
    }

    print("Using defaults (you can change file to override).")
    print("Bot token:", config["bot_token"][:10] + "..." )  # hide full token in console

    # We'll poll getUpdates and process messages from the configured user_chat_id
    offset = None
    print("Polling bot getUpdates... Send /hello to your bot from your phone.")
    while True:
        try:
            data = bot_get_updates(config["bot_token"], offset=offset, timeout=GETUPDATES_TIMEOUT)
            if not data.get("ok"):
                time.sleep(1)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                chat = msg.get("chat", {})
                chat_id = chat.get("id")
                text = (msg.get("text") or "").strip()
                print(f"Update from {chat_id}: {text[:100]}")
                # Only accept commands from configured user_chat_id for safety
                if str(chat_id) != str(config["user_chat_id"]):
                    bot_send(config["bot_token"], chat_id, "This bot is private. Use the configured account.")
                    continue
                # Process command
                try:
                    process_command(text, chat_id, config)
                except Exception as e:
                    traceback.print_exc()
                    bot_send(config["bot_token"], chat_id, "Error processing command: " + str(e))
            time.sleep(0.5)
        except KeyboardInterrupt:
            print("Interrupted by user. Exiting.")
            break
        except Exception as e:
            print("Main loop exception:", e)
            time.sleep(2)

if __name__ == "__main__":
    main_loop()
