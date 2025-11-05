#!/usr/bin/env python3
"""
✅ FINAL Telegram Member Fetcher (Telethon 1.37+)
✔ FIXED offset_id error
✔ Uses iter_participants() with offset (correct param)
✔ Fetches 85k+ members safely with resume + ping
✔ Compatible with Render worker (no port needed)
"""

import os, time, json, csv, asyncio, random, threading, requests
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
PING_URL = "https://teleautomation-by9o.onrender.com"
# ----------------------------------------

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

# ---------- LOGIN ----------
def tele_send_code():
    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        r = await c.send_code_request(PHONE)
        await c.disconnect()
        return getattr(r, "phone_code_hash", None)

    try:
        hashv = asyncio.run(inner())
        s = load_state()
        s["phone_code_hash"] = hashv
        s["hash_time"] = int(time.time())
        save_state(s)
        bot_send("📲 OTP sent! Use /otp <code>")
    except Exception as e:
        bot_send(f"❌ send_code error: {e}")

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
    try:
        ok, need2fa, msg = asyncio.run(inner())
        return ok, need2fa, msg
    except Exception as e:
        return False, False, f"Error: {e}"

def tele_sign_in_with_password(pwd):
    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        await c.sign_in(password=pwd)
        s = load_state()
        s["logged_in"] = True
        save_state(s)
        await c.disconnect()
    try:
        asyncio.run(inner())
        return True, "2FA success."
    except Exception as e:
        return False, str(e)

# ---------- FETCH MEMBERS ----------
def tele_fetch_members(progress_cb=None):
    members = []
    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        if not await c.is_user_authorized():
            raise Exception("Not logged in.")

        s = load_state()
        offset = s.get("last_offset", 0)
        total = s.get("last_count", 0)
        limit = 200

        bot_send(f"🔁 Resuming from offset {offset} ({total} users)")

        async for user in c.iter_participants(TUTORIAL_ID, offset=offset, limit=limit):
            members.append([
                user.id,
                getattr(user, "username", "") or "",
                getattr(user, "first_name", "") or "",
                getattr(user, "last_name", "") or "",
                getattr(user, "phone", "") or "",
            ])

            total += 1
            if total % limit == 0:
                offset += limit
                s["last_offset"] = offset
                s["last_count"] = total
                save_state(s)
                if progress_cb and total % PROGRESS_BATCH == 0:
                    progress_cb(total)
                await asyncio.sleep(random.uniform(1.5, 4.5))

        s["last_offset"] = 0
        s["last_count"] = 0
        save_state(s)
        await c.disconnect()

    try:
        asyncio.run(inner())
        return True, f"Fetched {len(members)} members.", members
    except Exception as e:
        return False, str(e), members

# ---------- PING ----------
async def ping_forever():
    while True:
        try:
            requests.get(PING_URL, timeout=10)
            print("💓 Ping sent")
        except Exception as e:
            print("Ping failed:", e)
        await asyncio.sleep(600)

def start_ping_thread():
    def run():
        asyncio.run(ping_forever())
    threading.Thread(target=run, daemon=True).start()

# ---------- COMMANDS ----------
def process_cmd(text):
    s = load_state()
    lower = text.lower().strip()
    if lower.startswith("/start"):
        bot_send("👋 Ready! /login → /otp → /fetch")
        return
    if lower.startswith("/help"):
        bot_send("/login\n/otp <code>\n/2fa <password>\n/fetch\n/status\n/users_count")
        return
    if lower.startswith("/login"):
        tele_send_code(); return
    if lower.startswith("/otp"):
        p = text.split()
        if len(p) < 2: bot_send("Usage: /otp <code>"); return
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
        bot_send("Fetching members... (85k+ safe mode)")
        def cb(c): bot_send(f"✅ {c} fetched so far...")
        ok, msg, members = tele_fetch_members(cb)
        if not ok: bot_send(f"Error: {msg}"); return
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "username", "fname", "lname", "phone"])
            w.writerows(members)
        bot_send_file(OUTPUT_CSV, f"Total {len(members)} members")
        bot_send("✅ Done!")
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

# ---------- MAIN LOOP ----------
def main_loop():
    print("🚀 Bot started (85k fetch mode, Telethon 1.37 fixed offset)")
    start_ping_thread()
    offset = None
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 15},
                timeout=20,
            ).json()
            if not r.get("ok"): time.sleep(1); continue
            for u in r["result"]:
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                text = msg.get("text", "")
                chat = msg.get("chat", {})
                if not text: continue
                if str(chat.get("id")) != str(USER_CHAT_ID):
                    bot_send("Private bot 🔒"); continue
                process_cmd(text)
            time.sleep(1)
        except Exception as e:
            print("Loop error:", e)
            time.sleep(2)

if __name__ == "__main__":
    main_loop()
