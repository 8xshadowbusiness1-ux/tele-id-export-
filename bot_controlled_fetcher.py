#!/usr/bin/env python3
"""
💎 FINAL TELEGRAM MEMBER FETCHER (90K+ VERSION - RENDER FREE FIX)
✔ FIXED: Added dummy Flask server to bind port for Render Web Service (free tier)
✔ Multi-filter (A–Z) fetching for 90k+
✔ FloodWait & network retry handling
✔ AuthRestartError retry in login
✔ Auto resume & ping for Render
✔ Compatible with Telethon 1.37+
"""
import os, time, json, csv, asyncio, random, threading, requests, traceback
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, AuthRestartError
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from flask import Flask  # NEW: For dummy HTTP server

# ---------------- CONFIG ----------------
API_ID = 18085901
API_HASH = "baa5a6ca152c717e88ea45f888d3af74"
PHONE = "+918436452250"
BOT_TOKEN = "8254353086:AAEMim12HX44q0XYaFWpbB3J7cxm4VWprEc"
USER_CHAT_ID = 1602198875
TUTORIAL_ID = -1002647054427 # Your target channel/group ID
OUTPUT_CSV = "tutorial_members.csv"
STATE_FILE = "state.json"
PROGRESS_BATCH = 500
PING_URL = "https://teleautomation-by9o.onrender.com"
# ----------------------------------------

# NEW: Dummy Flask app to satisfy Render port binding (free Web Service)
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot is running! 🚀"

# ---------- Telegram Bot Functions ----------
def bot_send(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": USER_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception as e:
        print("bot_send error:", e)

def bot_send_file(path, caption=""):
    try:
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                data={"chat_id": USER_CHAT_ID, "caption": caption},
                files={"document": f},
                timeout=180,
            )
    except Exception as e:
        print("bot_send_file error:", e)

def load_state():
    try:
        return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    except Exception:
        return {}

def save_state(s):
    json.dump(s, open(STATE_FILE, "w", encoding="utf-8"), indent=2)

# ---------- Login System (FIXED: Retry on AuthRestartError) ----------
def tele_send_code():
    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        r = await c.send_code_request(PHONE)
        await c.disconnect()
        return getattr(r, "phone_code_hash", None)
    
    retries = 3
    while retries > 0:
        try:
            hashv = asyncio.run(inner())
            s = load_state()
            s["phone_code_hash"] = hashv
            s["hash_time"] = int(time.time())
            save_state(s)
            bot_send("📲 OTP sent! Use /otp <code>")
            return
        except AuthRestartError as e:
            print(f"AuthRestartError: {e} - Retrying in 5s...")
            time.sleep(5)
            retries -= 1
        except Exception as e:
            bot_send(f"❌ send_code error: {e}")
            return
    bot_send("❌ Max retries exceeded for send_code.")

def tele_sign_in_with_code(code):
    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        s = load_state()
        hashv = s.get("phone_code_hash")
        if not hashv:
            r = await c.send_code_request(PHONE)
            s["phone_code_hash"] = getattr(r, "phone_code_hash", "")
            save_state(s)
            await c.disconnect()
            return (False, False, "Code expired. Sent again.")
        try:
            await c.sign_in(PHONE, code, phone_code_hash=hashv)
            s["logged_in"] = True
            save_state(s)
            await c.disconnect()
            return (True, False, "✅ Login successful.")
        except SessionPasswordNeededError:
            await c.disconnect()
            return (True, True, "🔐 2FA required.")
    
    retries = 3
    while retries > 0:
        try:
            ok, need2fa, msg = asyncio.run(inner())
            return ok, need2fa, msg
        except AuthRestartError as e:
            print(f"AuthRestartError in sign_in: {e} - Retrying...")
            time.sleep(5)
            retries -= 1
        except Exception as e:
            return False, False, f"Error: {e}"
    return False, False, "Max retries exceeded."

def tele_sign_in_with_password(pwd):
    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        await c.sign_in(password=pwd)
        s = load_state()
        s["logged_in"] = True
        save_state(s)
        await c.disconnect()
    
    retries = 3
    while retries > 0:
        try:
            asyncio.run(inner())
            return True, "2FA success."
        except AuthRestartError as e:
            print(f"AuthRestartError in 2FA: {e} - Retrying...")
            time.sleep(5)
            retries -= 1
        except Exception as e:
            return False, str(e)
    return False, "Max retries exceeded."

# ---------- Multi-Filter Fetch System ----------
def tele_fetch_members(progress_cb=None):
    members = []

    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        if not await c.is_user_authorized():
            raise Exception("Not logged in.")

        s = load_state()
        total = s.get("last_count", 0)
        limit = 200

        filters = [""] + [chr(i) for i in range(97, 123)] # '', a-z

        for flt in filters:
            offset = 0
            bot_send(f"🔎 Fetching batch for '{flt or 'all'}'...")
            while True:
                try:
                    result = await c(GetParticipantsRequest(
                        channel=TUTORIAL_ID,
                        filter=ChannelParticipantsSearch(flt),
                        offset=offset,
                        limit=limit,
                        hash=0
                    ))

                    if not result.users:
                        break

                    for user in result.users:
                        members.append([
                            user.id,
                            getattr(user, "username", "") or "",
                            getattr(user, "first_name", "") or "",
                            getattr(user, "last_name", "") or "",
                            getattr(user, "phone", "") or "",
                        ])

                    total += len(result.users)
                    offset += len(result.users)
                    s["last_count"] = total
                    save_state(s)

                    if progress_cb and total % PROGRESS_BATCH == 0:
                        progress_cb(total)

                    await asyncio.sleep(random.uniform(1.0, 2.5))

                except FloodWaitError as fw:
                    bot_send(f"⏸ FloodWait: waiting {fw.seconds}s")
                    await asyncio.sleep(fw.seconds + 5)
                    continue
                except Exception as e:
                    bot_send(f"⚠️ Error: {e}, retrying in 10s")
                    await asyncio.sleep(10)
                    continue

        s["last_count"] = 0
        save_state(s)
        await c.disconnect()

    try:
        asyncio.run(inner())
        # Deduplicate by user.id
        unique = {}
        for u in members:
            unique[u[0]] = u
        members = list(unique.values())
        return True, f"Fetched {len(members)} unique members.", members
    except Exception as e:
        traceback.print_exc()
        return False, str(e), members

# ---------- Ping System ----------
async def ping_forever():
    while True:
        try:
            requests.get(PING_URL, timeout=10)
            print("💓 Ping sent to Render")
        except Exception as e:
            print("Ping failed:", e)
        await asyncio.sleep(600)

def start_ping_thread():
    def run():
        asyncio.run(ping_forever())
    threading.Thread(target=run, daemon=True).start()

# ---------- Command Handler ----------
def process_cmd(text):
    s = load_state()
    lower = text.lower().strip()
    if lower.startswith("/start"):
        bot_send("👋 Ready! Commands: /login → /otp → /fetch → /status → /users_count")
        return
    if lower.startswith("/login"):
        tele_send_code(); return
    if lower.startswith("/otp"):
        p = text.split()
        if len(p) < 2:
            bot_send("Usage: /otp <code>")
            return
        ok, need2fa, msg = tele_sign_in_with_code(p[1])
        bot_send(msg)
        if need2fa: bot_send("Send /2fa <password>")
        return
    if lower.startswith("/2fa"):
        p = text.split(maxsplit=1)
        if len(p) < 2: bot_send("Usage: /2fa <password>"); return
        ok, msg = tele_sign_in_with_password(p[1])
        bot_send(msg)
        return
    if lower.startswith("/fetch"):
        if not s.get("logged_in"):
            bot_send("Login first."); return
        bot_send("Fetching members... (90k+ safe mode)")
        def cb(c): bot_send(f"✅ {c} fetched so far...")
        ok, msg, members = tele_fetch_members(cb)
        if not ok:
            bot_send(f"Error: {msg}")
            return
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "username", "fname", "lname", "phone"])
            w.writerows(members)
        bot_send_file(OUTPUT_CSV, f"Total {len(members)} members fetched ✅")
        bot_send("✅ Completed Successfully!")
        return
    if lower.startswith("/status"):
        bot_send(json.dumps(s, indent=2)); return
    if lower.startswith("/users_count"):
        if os.path.exists(OUTPUT_CSV):
            c = sum(1 for _ in open(OUTPUT_CSV, encoding="utf-8")) - 1
            bot_send(f"{c} users in CSV")
        else:
            bot_send("No CSV yet")
        return
    bot_send("Unknown command")

# ---------- Main Loop ----------
def main_loop():
    print("🚀 Bot started (Telethon 1.37+ | 90k+ mode active)")
    offset = None
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 15},
                timeout=20,
            ).json()
            if not r.get("ok"):
                time.sleep(1)
                continue
            for u in r["result"]:
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                text = msg.get("text", "")
                chat = msg.get("chat", {})
                if not text:
                    continue
                if str(chat.get("id")) != str(USER_CHAT_ID):
                    bot_send("🔒 Unauthorized user detected")
                    continue
                process_cmd(text)
            time.sleep(1)
        except Exception as e:
            print("Loop error:", e)
            time.sleep(3)

if __name__ == "__main__":
    # Start ping and bot in threads
    start_ping_thread()
    threading.Thread(target=main_loop, daemon=True).start()
    
    # Run dummy Flask server for Render port binding
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting dummy HTTP server on port {port} for Render...")
    app.run(host='0.0.0.0', port=port, debug=False)
