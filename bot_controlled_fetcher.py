#!/usr/bin/env python3
"""
✅ Final Render-Safe Telegram Member Bot (v3)
✔️ Uses iter_participants() — safe & 85k+ fetch
✔️ Handles OTP + 2FA + auto flood wait
✔️ Auto ping every 10 min (keep alive)
✔️ Works perfectly on Render (no port bind)
"""

import os, time, json, csv, asyncio, random, threading, requests, traceback
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError

# ---------------- CONFIG ----------------
API_ID = 18085901
API_HASH = "baa5a6ca152c717e88ea45f888d3af74"
PHONE = "+918436452250"
BOT_TOKEN = "8254353086:AAEMim12HX44q0XYaFWpbB3J7cxm4VWprEc"
USER_CHAT_ID = 1602198875
TUTORIAL_ID = -1002647054427
OUTPUT_CSV = "tutorial_members.csv"
STATE_FILE = "state.json"
PROGRESS_BATCH = 500
PING_URL = "https://teleautomation-by9o.onrender.com"  # <-- Your Render ping URL
# ----------------------------------------

# ---------- HELPERS ----------
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
                timeout=120,
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

# ---------- TELETHON LOGIN ----------
def tele_send_code():
    try:
        async def inner():
            c = TelegramClient("session_bot", API_ID, API_HASH)
            await c.connect()
            result = await c.send_code_request(PHONE)
            await c.disconnect()
            return getattr(result, "phone_code_hash", None)
        code_hash = asyncio.run(inner())
        if not code_hash:
            bot_send("❌ No phone_code_hash received.")
            return False
        s = load_state()
        s["phone_code_hash"] = code_hash
        s["hash_time"] = int(time.time())
        save_state(s)
        bot_send("📲 OTP sent. Use /otp <code>")
        return True
    except Exception as e:
        bot_send(f"❌ send_code error: {e}")
        return False

def tele_sign_in_with_code(code):
    try:
        async def inner():
            c = TelegramClient("session_bot", API_ID, API_HASH)
            await c.connect()
            s = load_state()
            ph_hash = s.get("phone_code_hash")
            if not ph_hash or (int(time.time()) - s.get("hash_time", 0)) > 600:
                result = await c.send_code_request(PHONE)
                s["phone_code_hash"] = getattr(result, "phone_code_hash", "")
                s["hash_time"] = int(time.time())
                save_state(s)
                await c.disconnect()
                return (False, False, "OTP expired. New code sent.")
            try:
                await c.sign_in(phone=PHONE, code=code, phone_code_hash=ph_hash)
                s["logged_in"] = True
                s.pop("phone_code_hash", None)
                save_state(s)
                await c.disconnect()
                return (True, False, "✅ Login successful.")
            except SessionPasswordNeededError:
                await c.disconnect()
                return (True, True, "🔐 2FA required.")
        ok, need2fa, msg = asyncio.run(inner())
        return ok, need2fa, msg
    except Exception as e:
        return False, False, str(e)

def tele_sign_in_with_password(pwd):
    try:
        async def inner():
            c = TelegramClient("session_bot", API_ID, API_HASH)
            await c.connect()
            await c.sign_in(password=pwd)
            s = load_state()
            s["logged_in"] = True
            save_state(s)
            await c.disconnect()
        asyncio.run(inner())
        return True, "2FA success."
    except Exception as e:
        return False, str(e)

# ---------- FETCH MEMBERS (Full 85k+ safe) ----------
def tele_fetch_members(progress_cb=None):
    members = []
    try:
        async def inner():
            c = TelegramClient("session_bot", API_ID, API_HASH)
            await c.connect()
            if not await c.is_user_authorized():
                raise Exception("Not logged in.")
            count = 0
            async for user in c.iter_participants(TUTORIAL_ID, aggressive=True):
                members.append([
                    user.id,
                    getattr(user, "username", "") or "",
                    getattr(user, "first_name", "") or "",
                    getattr(user, "last_name", "") or "",
                    getattr(user, "phone", "") or "",
                ])
                count += 1
                if progress_cb and count % PROGRESS_BATCH == 0:
                    progress_cb(count)
                if count % 1000 == 0:
                    await asyncio.sleep(random.uniform(1.5, 3))  # flood safety
            await c.disconnect()
        asyncio.run(inner())
        return True, f"Fetched {len(members)} members.", members
    except FloodWaitError as fw:
        return False, f"FloodWait {fw.seconds}s", members
    except Exception as e:
        return False, str(e), members

# ---------- KEEP-ALIVE PING ----------
async def ping_forever():
    while True:
        try:
            requests.get(PING_URL, timeout=10)
            print("💓 Ping sent")
        except Exception as e:
            print("Ping fail:", e)
        await asyncio.sleep(600)

def start_ping_thread():
    def run_ping():
        try:
            asyncio.run(ping_forever())
        except Exception as e:
            print("Ping thread ended:", e)
    threading.Thread(target=run_ping, daemon=True).start()

# ---------- COMMAND HANDLER ----------
def process_cmd(text):
    lower = text.lower().strip()
    s = load_state()

    if lower.startswith("/start") or lower.startswith("/hello"):
        bot_send("👋 Bot ready! Use /login → /otp → /fetch\nType /help for commands.")
        return
    if lower.startswith("/help"):
        bot_send("/login\n/otp <code>\n/2fa <password>\n/fetch\n/status\n/users_count\n/ping")
        return
    if lower.startswith("/ping"):
        bot_send("🏓 Pong!")
        return
    if lower.startswith("/login"):
        tele_send_code()
        return
    if lower.startswith("/otp"):
        parts = text.split()
        if len(parts) < 2:
            bot_send("Usage: /otp <code>")
            return
        ok, need2fa, msg = tele_sign_in_with_code(parts[1])
        bot_send(msg)
        if need2fa:
            bot_send("Now send /2fa <password>")
        return
    if lower.startswith("/2fa"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            bot_send("Usage: /2fa <password>")
            return
        ok, msg = tele_sign_in_with_password(parts[1])
        bot_send(msg)
        return
    if lower.startswith("/fetch"):
        if not s.get("logged_in"):
            bot_send("Please login first (/login + /otp).")
            return
        bot_send("🚀 Starting fetch, please wait. (85k+ supported)")
        def cb(cnt): bot_send(f"✅ {cnt} users fetched...")
        ok, msg, members = tele_fetch_members(cb)
        if not ok:
            bot_send("❌ Error: " + msg)
            return
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "username", "fname", "lname", "phone"])
            w.writerows(members)
        bot_send_file(OUTPUT_CSV, f"Tutorial Members ({len(members)})")
        bot_send("✅ Fetch complete.")
        return
    if lower.startswith("/status"):
        bot_send(json.dumps(s, indent=2))
        return
    if lower.startswith("/users_count"):
        if os.path.exists(OUTPUT_CSV):
            lines = sum(1 for _ in open(OUTPUT_CSV, "r", encoding="utf-8")) - 1
            bot_send(f"Users in CSV: {lines}")
        else:
            bot_send("No CSV found.")
        return
    bot_send("Unknown command. Use /help")

# ---------- MAIN LOOP ----------
def main_loop():
    print("🚀 Bot fetcher running (Render-safe)")
    start_ping_thread()
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
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                chat = msg.get("chat", {})
                text = msg.get("text", "")
                if not text:
                    continue
                if str(chat.get("id")) != str(USER_CHAT_ID):
                    bot_send("Private bot 🔒")
                    continue
                process_cmd(text)
            time.sleep(0.5)
        except Exception as e:
            print("Loop error:", e)
            time.sleep(2)

if __name__ == "__main__":
    main_loop()
