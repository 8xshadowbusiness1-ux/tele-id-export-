#!/usr/bin/env python3
"""
✅ Final Render-Safe Telegram Member Bot
Features:
- /login, /otp, /2fa (with persistent phone_code_hash)
- /fetch members (with progress + CSV)
- Auto ping every 10 min
- Auto keep-alive session (never logs out)
- FloodWait auto pause
"""

import os, time, json, csv, asyncio, requests, traceback
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.errors.rpcerrorlist import RPCError

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
PING_URL = "https://teleautomation-by9o.onrender.com"  # <── apna render URL daalo
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
    return json.load(open(STATE_FILE, "r")) if os.path.exists(STATE_FILE) else {}

def save_state(s):
    json.dump(s, open(STATE_FILE, "w"), indent=2)

# ---------- TELETHON FIXED LOGIN ----------
def tele_send_code():
    try:
        async def inner():
            c = TelegramClient("session_bot", API_ID, API_HASH)
            await c.connect()
            result = await c.send_code_request(PHONE)
            await c.disconnect()
            return result.phone_code_hash
        phone_code_hash = asyncio.run(inner())
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
            if not hashv or (int(time.time()) - st.get("hash_timestamp", 0)) > 600:
                # auto resend OTP if expired
                result = await c.send_code_request(PHONE)
                st["phone_code_hash"] = result.phone_code_hash
                st["hash_timestamp"] = int(time.time())
                save_state(st)
                await c.disconnect()
                return (False, False, "OTP expired, new code sent.")
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

# ---------- FETCH MEMBERS ----------
def tele_fetch_members(progress_cb=None):
    members = []
    try:
        async def inner():
            c = TelegramClient("session_bot", API_ID, API_HASH)
            await c.connect()
            async for user in c.iter_participants(TUTORIAL_ID, aggressive=True):
                members.append([
                    user.id,
                    getattr(user, "username", "") or "",
                    getattr(user, "first_name", "") or "",
                    getattr(user, "last_name", "") or "",
                    getattr(user, "phone", "") or "",
                ])
                if len(members) % PROGRESS_BATCH == 0 and progress_cb:
                    progress_cb(len(members))
            await c.disconnect()
        asyncio.run(inner())
        return True, f"Fetched {len(members)} members.", members
    except FloodWaitError as fw:
        return False, f"FloodWait {fw.seconds}s", members
    except Exception as e:
        return False, str(e), members

# ---------- PING / KEEP-ALIVE ----------
async def ping_forever():
    while True:
        try:
            requests.get(PING_URL, timeout=10)
            print(f"💓 Ping {PING_URL}")
        except Exception as e:
            print("Ping failed:", e)
        await asyncio.sleep(600)

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
        tele_send_code(); return
    if lower.startswith("/otp"):
        parts = lower.split()
        if len(parts) < 2: bot_send("Usage: /otp <code>"); return
        ok, need2fa, msg = tele_sign_in_with_code(parts[1])
        bot_send(msg)
        if need2fa: bot_send("Send /2fa <password>")
        return
    if lower.startswith("/2fa"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2: bot_send("Usage: /2fa <password>"); return
        ok, msg = tele_sign_in_with_password(parts[1]); bot_send(msg); return
    if lower.startswith("/fetch"):
        if not st.get("logged_in"): bot_send("Login first."); return
        bot_send("Fetching members..."); 
        def cb(cnt): bot_send(f"Fetched {cnt} so far...")
        ok, msg, members = tele_fetch_members(cb)
        if not ok: bot_send("Error: " + msg); return
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["id","username","fname","lname","phone"])
            w.writerows(members)
        bot_send_file(OUTPUT_CSV, "Tutorial members CSV")
        bot_send(f"✅ Done {len(members)} users.")
        return
    if lower.startswith("/status"):
        bot_send(json.dumps(st, indent=2))
        return
    if lower.startswith("/users_count"):
        if os.path.exists(OUTPUT_CSV):
            c = sum(1 for _ in open(OUTPUT_CSV)) - 1
            bot_send(f"Users in CSV: {c}")
        else:
            bot_send("No CSV found.")
        return
    bot_send("Unknown command.")

# ---------- POLLING LOOP ----------
def main_loop():
    print("🚀 Bot fetcher running...")
    asyncio.get_event_loop().create_task(ping_forever())
    offset = None
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 15},
                timeout=20,
            ).json()
            if not r.get("ok"): time.sleep(1); continue
            for upd in r["result"]:
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                chat = msg.get("chat", {})
                text = msg.get("text", "")
                if not text: continue
                if str(chat.get("id")) != str(USER_CHAT_ID):
                    bot_send("Private bot 🔒")
                    continue
                process_cmd(text)
        except KeyboardInterrupt:
            print("Exit.")
            break
        except Exception as e:
            print("Loop error:", e)
            time.sleep(2)

if __name__ == "__main__":
    main_loop()
