#!/usr/bin/env python3
"""
💎 ULTIMATE TELEGRAM MEMBER FETCHER (90K+ FINAL VERSION)
✔ LIVE LOGS in Render (print() added)
✔ LIVE STATUS in Bot (/status)
✔ PING URL = https://tele-id-export.onrender.com
✔ Flask + Ping Thread → NO SLEEP
✔ FloodWait + Resume + Dedup
✔ Multi-filter A-Z → 10k limit bypass
✔ Telethon 1.37+ | Render Free Tier
"""
import os, time, json, csv, asyncio, random, threading, requests, traceback
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, AuthRestartError
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from flask import Flask

# ---------------- CONFIG ----------------
API_ID = 18085901
API_HASH = "baa5a6ca152c717e88ea45f888d3af74"
PHONE = "+918436452250"
BOT_TOKEN = "8254353086:AAEMim12HX44q0XYaFWpbB3J7cxm4VWprEc"
USER_CHAT_ID = 1602198875
TUTORIAL_ID = -1001823169797
OUTPUT_CSV = "tutorial_members.csv"
STATE_FILE = "state.json"
PROGRESS_BATCH = 500
PING_URL = "https://tele-id-export.onrender.com"  # ← TUMHARA URL
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Running! 90k+ Fetching... Live Logs Active"

# ---------- LOGGING + BOT SEND ----------
def log_print(*args):
    msg = " ".join(map(str, args))
    print(f"[LIVE] {msg}")
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": USER_CHAT_ID, "text": f"LOG: {msg}"},
            timeout=10
        )
    except: pass

def bot_send(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": USER_CHAT_ID, "text": text},
            timeout=10,
        )
        log_print("BOT →", text)
    except Exception as e:
        log_print("bot_send error:", e)

def bot_send_file(path, caption=""):
    try:
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                data={"chat_id": USER_CHAT_ID, "caption": caption},
                files={"document": f},
                timeout=180,
            )
        log_print("FILE SENT:", path)
    except Exception as e:
        log_print("bot_send_file error:", e)

# ---------- STATE ----------
def load_state():
    try:
        return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    except:
        return {}

def save_state(s):
    try:
        json.dump(s, open(STATE_FILE, "w", encoding="utf-8"), indent=2)
        log_print("STATE SAVED")
    except Exception as e:
        log_print("save_state error:", e)

# ---------- LOGIN ----------
def tele_send_code():
    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        r = await c.send_code_request(PHONE)
        await c.disconnect()
        return getattr(r, "phone_code_hash", None)
    for _ in range(3):
        try:
            hashv = asyncio.run(inner())
            s = load_state()
            s["phone_code_hash"] = hashv
            s["hash_time"] = int(time.time())
            save_state(s)
            bot_send("OTP sent! /otp <code>")
            return
        except AuthRestartError:
            time.sleep(5)
        except Exception as e:
            bot_send(f"send_code error: {e}")
            return

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
            return (False, False, "Code expired.")
        try:
            await c.sign_in(PHONE, code, phone_code_hash=hashv)
            s["logged_in"] = True
            save_state(s)
            await c.disconnect()
            return (True, False, "Login success!")
        except SessionPasswordNeededError:
            await c.disconnect()
            return (True, True, "2FA needed.")
    for _ in range(3):
        try:
            ok, need2fa, msg = asyncio.run(inner())
            return ok, need2fa, msg
        except AuthRestartError:
            time.sleep(5)
        except Exception as e:
            return False, False, f"Error: {e}"
    return False, False, "Max retries."

def tele_sign_in_with_password(pwd):
    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        await c.sign_in(password=pwd)
        s = load_state()
        s["logged_in"] = True
        save_state(s)
        await c.disconnect()
    for _ in range(3):
        try:
            asyncio.run(inner())
            return True, "2FA success!"
        except AuthRestartError:
            time.sleep(5)
        except Exception as e:
            return False, str(e)
    return False, "Max retries."

# ---------- 90K+ FETCH (LIVE LOGS) ----------
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
        filters = [""] + [chr(i) for i in range(97, 123)]
        for flt in filters:
            offset = 0
            name = flt or 'all'
            bot_send(f"Starting: '{name}'")
            log_print(f"Starting filter: {name}")
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
                        log_print(f"Filter '{name}' DONE")
                        break
                    batch = len(result.users)
                    for user in result.users:
                        members.append([
                            user.id,
                            getattr(user, "username", "") or "",
                            getattr(user, "first_name", "") or "",
                            getattr(user, "last_name", "") or "",
                            getattr(user, "phone", "") or "",
                        ])
                    total += batch
                    offset += batch
                    s["last_count"] = total
                    save_state(s)
                    log_print(f"+{batch} | Total: {total} | Filter: {name}")
                    if progress_cb and total % PROGRESS_BATCH == 0:
                        progress_cb(total)
                    await asyncio.sleep(random.uniform(1.0, 2.5))
                except FloodWaitError as fw:
                    msg = f"FloodWait: {fw.seconds}s"
                    bot_send(msg)
                    log_print(msg)
                    await asyncio.sleep(fw.seconds + 5)
                    continue
                except Exception as e:
                    log_print(f"Error: {e} - Retrying...")
                    await asyncio.sleep(10)
                    continue
        s["last_count"] = 0
        save_state(s)
        await c.disconnect()
    try:
        asyncio.run(inner())
        unique = {u[0]: u for u in members}
        members = list(unique.values())
        final = f"Fetched {len(members)} unique members!"
        bot_send(final)
        log_print("FINAL:", final)
        return True, final, members
    except Exception as e:
        log_print("FATAL ERROR:", e)
        traceback.print_exc()
        return False, str(e), members

# ---------- PING ----------
async def ping_forever():
    while True:
        try:
            requests.get(PING_URL, timeout=10)
            log_print("PING SENT")
        except:
            log_print("PING FAILED")
        await asyncio.sleep(600)

def start_ping_thread():
    threading.Thread(target=lambda: asyncio.run(ping_forever()), daemon=True).start()

# ---------- COMMANDS ----------
def process_cmd(text):
    s = load_state()
    lower = text.lower().strip()
    if lower.startswith("/start"):
        bot_send("Ready! /login → /otp → /fetch → /status")
        return
    if lower.startswith("/login"):
        tele_send_code(); return
    if lower.startswith("/otp"):
        code = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""
        ok, need2fa, msg = tele_sign_in_with_code(code)
        bot_send(msg)
        if need2fa: bot_send("Send /2fa <password>")
        return
    if lower.startswith("/2fa"):
        pwd = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""
        ok, msg = tele_sign_in_with_password(pwd)
        bot_send(msg)
        return
    if lower.startswith("/fetch"):
        if not s.get("logged_in"):
            bot_send("Login first!"); return
        bot_send("90k+ Fetch STARTED...")
        def cb(c): bot_send(f"{c} fetched so far...")
        ok, msg, members = tele_fetch_members(cb)
        if not ok:
            bot_send(f"Error: {msg}")
            return
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "username", "fname", "lname", "phone"])
            w.writerows(members)
        bot_send_file(OUTPUT_CSV, f"Total {len(members)} members!")
        bot_send("COMPLETED!")
        return
    if lower.startswith("/status"):
        status = json.dumps(s, indent=2)
        bot_send(f"Status:\n{status}")
        log_print("STATUS REQUESTED:\n", status)
        return
    if lower.startswith("/users_count"):
        if os.path.exists(OUTPUT_CSV):
            c = sum(1 for _ in open(OUTPUT_CSV)) - 1
            bot_send(f"{c} users in CSV")
        else:
            bot_send("No CSV yet")
        return
    bot_send("Unknown command")

# ---------- MAIN LOOP ----------
def main_loop():
    log_print("BOT STARTED")
    offset = None
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 15},
                timeout=20,
            ).json()
            if not r.get("ok"):
                time.sleep(1); continue
            for u in r["result"]:
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                if not text or str(chat_id) != str(USER_CHAT_ID):
                    continue
                process_cmd(text)
            time.sleep(1)
        except Exception as e:
            log_print("LOOP ERROR:", e)
            time.sleep(3)

if __name__ == "__main__":
    start_ping_thread()
    threading.Thread(target=main_loop, daemon=True).start()
    port = int(os.environ.get('PORT', 10000))
    log_print(f"HTTP SERVER STARTED on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
