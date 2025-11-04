#!/usr/bin/env python3
"""
✅ Final Render-Safe Telegram Member Bot (85k+ fetch ready)
Notes:
- Keeps phone_code_hash persistently in state.json
- /login, /otp, /2fa, /fetch, /status, /users_count, /ping supported
- Proper pagination using offset_id for large fetches
- FloodWait handling + small delays to be safe
- Ping/keep-alive runs in a background thread (avoids asyncio loop warnings)
"""

import os
import time
import json
import csv
import asyncio
import requests
import traceback
import random
import threading

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
PING_URL = "https://teleautomation-by9o.onrender.com"  # <-- put your render URL here
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
            files = {"document": f}
            data = {"chat_id": USER_CHAT_ID, "caption": caption}
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                data=data,
                files=files,
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
        phone_code_hash = asyncio.run(inner())
        if not phone_code_hash:
            bot_send("❌ send_code returned no phone_code_hash.")
            return False
        st = load_state()
        st["phone_code_hash"] = phone_code_hash
        st["hash_timestamp"] = int(time.time())
        save_state(st)
        bot_send("📲 OTP sent! Please send /otp <code>.")
        return True
    except Exception as e:
        bot_send(f"❌ send_code error: {e}")
        return False

def tele_sign_in_with_code(code):
    try:
        async def inner():
            c = TelegramClient("session_bot", API_ID, API_HASH)
            await c.connect()
            st = load_state()
            hashv = st.get("phone_code_hash")
            # if missing or expired, auto resend
            if not hashv or (int(time.time()) - st.get("hash_timestamp", 0)) > 600:
                result = await c.send_code_request(PHONE)
                st["phone_code_hash"] = getattr(result, "phone_code_hash", None)
                st["hash_timestamp"] = int(time.time())
                save_state(st)
                await c.disconnect()
                return (False, False, "OTP expired; new code sent. Please try /otp again.")
            try:
                await c.sign_in(phone=PHONE, code=code, phone_code_hash=hashv)
                st["logged_in"] = True
                st.pop("phone_code_hash", None)
                st.pop("hash_timestamp", None)
                save_state(st)
                await c.disconnect()
                return (True, False, "Login successful.")
            except SessionPasswordNeededError:
                await c.disconnect()
                return (True, True, "2FA required.")
        ok, needs2fa, msg = asyncio.run(inner())
        return ok, needs2fa, msg
    except Exception as e:
        return False, False, f"sign_in_code error: {e}"

def tele_sign_in_with_password(pwd):
    try:
        async def inner():
            c = TelegramClient("session_bot", API_ID, API_HASH)
            await c.connect()
            await c.sign_in(password=pwd)
            st = load_state()
            st["logged_in"] = True
            save_state(st)
            await c.disconnect()
        asyncio.run(inner())
        return True, "2FA success."
    except Exception as e:
        return False, f"2FA error: {e}"

# ---------- FETCH MEMBERS (offset_id pagination) ----------
def tele_fetch_members(progress_cb=None):
    members = []
    try:
        async def inner():
            c = TelegramClient("session_bot", API_ID, API_HASH)
            await c.connect()

            # ensure we're authorized
            if not await c.is_user_authorized():
                await c.disconnect()
                raise Exception("Not authorized. Please login first via /login + /otp.")

            last_id = 0  # offset_id uses user id to paginate: fetch users with id > last_id progressively
            batch_size = 200
            total = 0
            consecutive_empty = 0

            while True:
                try:
                    # Use offset_id (last_id) and limit=batch_size
                    batch = await c.get_participants(TUTORIAL_ID, offset_id=last_id, limit=batch_size)
                except TypeError:
                    # Fallback: older Telethon versions may require positional args
                    batch = await c.get_participants(TUTORIAL_ID, last_id, batch_size)
                except FloodWaitError as fw:
                    await c.disconnect()
                    raise fw

                if not batch:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break
                    await asyncio.sleep(1)
                    continue

                consecutive_empty = 0
                for user in batch:
                    members.append([
                        user.id,
                        getattr(user, "username", "") or "",
                        getattr(user, "first_name", "") or "",
                        getattr(user, "last_name", "") or "",
                        getattr(user, "phone", "") or "",
                    ])
                total += len(batch)

                # update last_id to last user in batch (offset_id expects message/user id to offset)
                last_id = batch[-1].id

                if progress_cb and total % PROGRESS_BATCH <= batch_size:
                    # send periodic progress
                    progress_cb(total)

                # small randomized pause between batches to reduce flood risk
                await asyncio.sleep(random.uniform(1.2, 2.5))

                # safety: break if we somehow loop too many times
                if total >= 300000:  # hard limit to avoid infinite loop (very large)
                    break

            await c.disconnect()

        asyncio.run(inner())
        return True, f"Fetched {len(members)} members.", members
    except FloodWaitError as fw:
        return False, f"FloodWait {fw.seconds}s", members
    except Exception as e:
        return False, str(e), members

# ---------- PING / KEEP-ALIVE (run in background thread) ----------
async def ping_forever():
    while True:
        try:
            requests.get(PING_URL, timeout=10)
            print(f"💓 Ping {PING_URL}")
        except Exception as e:
            print("Ping failed:", e)
        await asyncio.sleep(600)

def start_ping_thread():
    # Run ping_forever in a separate thread safely
    def runner():
        try:
            asyncio.run(ping_forever())
        except Exception as e:
            print("ping thread stopped:", e)
    t = threading.Thread(target=runner, daemon=True)
    t.start()

# ---------- COMMAND HANDLER ----------
def process_cmd(text):
    lower = text.lower().strip()
    st = load_state()

    if lower.startswith("/start") or lower.startswith("/hello"):
        bot_send("👋 Ready! Use /login → /otp → /fetch\nType /help for commands.")
        return
    if lower.startswith("/help"):
        bot_send("/login\n/otp <code>\n/2fa <pass>\n/fetch\n/status\n/users_count\n/ping")
        return
    if lower.startswith("/ping"):
        bot_send(f"Pong {time.strftime('%H:%M:%S')}")
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
            bot_send("Send /2fa <password>")
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
        if not st.get("logged_in"):
            bot_send("Login first (use /login + /otp).")
            return
        bot_send("Fetching members... This can take a while for 80k+ members. I will send progress updates.")
        def cb(cnt):
            bot_send(f"✅ Fetched {cnt} so far...")
        ok, msg, members = tele_fetch_members(progress_cb=cb)
        if not ok:
            bot_send("Error: " + msg)
            return
        try:
            with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "username", "fname", "lname", "phone"])
                w.writerows(members)
            bot_send_file(OUTPUT_CSV, "Tutorial members CSV")
            bot_send(f"✅ Done! Total {len(members)} users fetched.")
        except Exception as e:
            bot_send("Error saving/sending CSV: " + str(e))
        return
    if lower.startswith("/status"):
        bot_send(json.dumps(st, indent=2))
        return
    if lower.startswith("/users_count"):
        if os.path.exists(OUTPUT_CSV):
            try:
                c = sum(1 for _ in open(OUTPUT_CSV, "r", encoding="utf-8")) - 1
                bot_send(f"Users in CSV: {c}")
            except Exception as e:
                bot_send("Error reading CSV: " + str(e))
        else:
            bot_send("No CSV found.")
        return
    bot_send("Unknown command. Type /help")

# ---------- POLLING LOOP ----------
def main_loop():
    print("🚀 Bot fetcher running...")
    # start ping background thread
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
                try:
                    process_cmd(text)
                except Exception as e:
                    traceback.print_exc()
                    bot_send("Error processing command: " + str(e))
            # small sleep to avoid tight loop
            time.sleep(0.5)
        except KeyboardInterrupt:
            print("Exit by user.")
            break
        except Exception as e:
            print("Loop error:", e)
            time.sleep(2)

if __name__ == "__main__":
    main_loop()
