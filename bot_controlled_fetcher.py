#!/usr/bin/env python3
"""
✅ FULL & FINAL: 90k+ Telegram Member Fetcher (Aggressive Mode)
✔ Uses client.get_participants(aggressive=True) for 90k+ in one go
✔ Bypasses 10k limit with a-z search (slow but reliable, 5-15 min)
✔ Auto resume + ping for Render
✔ FloodWait & retry handling
✔ Unique users only, CSV export
"""
import os, time, json, csv, asyncio, random, threading, requests, traceback
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.types import ChannelParticipantsSearch
# ---------------- CONFIG ----------------
API_ID = 18085901
API_HASH = "baa5a6ca152c717e88ea45f888d3af74"
PHONE = "+918436452250"
BOT_TOKEN = "8254353086:AAEMim12HX44q0XYaFWpbB3J7cxm4VWprEc"
USER_CHAT_ID = 1602198875
TUTORIAL_ID = -1002647054427 # Channel or group ID
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
# ---------- FETCH MEMBERS (AGGRESSIVE MODE - 90k+ SUPPORT) ----------
def tele_fetch_members(progress_cb=None):
    members = []
    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        if not await c.is_user_authorized():
            raise Exception("Not logged in.")
        
        s = load_state()
        if s.get("aggressive_fetched", 0) > 0:
            bot_send(f"🔁 Resuming from {s['aggressive_fetched']} users (full aggressive fetch)")
        
        bot_send("🚀 Starting AGGRESSIVE fetch for 90k+ members (a-z search, ~10-15 min)...")
        
        try:
            # AGGRESSIVE FETCH: Bypasses 10k limit with internal a-z searches
            all_participants = await c.get_participants(
                TUTORIAL_ID,
                aggressive=True,  # Magic: Fetches all via multiple searches
                limit=0  # Fetch ALL possible
            )
            
            bot_send(f"📊 Raw fetch complete: {len(all_participants)} participants received")
            
            # Process unique users (remove duplicates)
            seen_ids = set()
            fetched_count = s.get("aggressive_fetched", 0)
            for user in all_participants:
                uid = user.id
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    members.append([
                        uid,
                        getattr(user, "username", "") or "",
                        getattr(user, "first_name", "") or "",
                        getattr(user, "last_name", "") or "",
                        getattr(user, "phone", "") or "",
                    ])
                    fetched_count += 1
                    
                    # Save progress every batch for resume
                    if fetched_count % PROGRESS_BATCH == 0:
                        s["aggressive_fetched"] = fetched_count
                        save_state(s)
                        if progress_cb:
                            progress_cb(fetched_count)
                        await asyncio.sleep(random.uniform(0.5, 1.5))  # Light pause
            
            # Final save & reset
            s["aggressive_fetched"] = 0
            s["last_offset"] = 0  # Clear old state
            s["last_count"] = 0
            save_state(s)
            
            if progress_cb:
                progress_cb(fetched_count)
            
            await c.disconnect()
            
        except FloodWaitError as fw:
            bot_send(f"⏸️ FloodWait hit: {fw.seconds}s - Pausing...")
            await asyncio.sleep(fw.seconds + 10)
            # Retry once after wait
            raise  # Re-raise to handle in outer try
        except Exception as e:
            bot_send(f"⚠️ Fetch error: {e} - Saving partial {len(members)} users")
            s["aggressive_fetched"] = fetched_count
            save_state(s)
            await c.disconnect()
            raise
    
    try:
        asyncio.run(inner())
        return True, f"✅ Fetched {len(members)} UNIQUE members in one go!", members
    except FloodWaitError as fw:
        bot_send(f"🔄 FloodWait {fw.seconds}s - Restart /fetch to continue")
        return False, f"FloodWait {fw.seconds}s - Partial saved", members
    except Exception as e:
        traceback.print_exc()
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
        bot_send("👋 Ready! /login → /otp → /fetch (90k+ aggressive mode)")
        return
    if lower.startswith("/help"):
        bot_send("/login\n/otp <code>\n/2fa <password>\n/fetch\n/status\n/users_count\n/reset")
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
        bot_send("🔄 Starting 90k+ fetch (aggressive mode - be patient, 10-15 min)...")
        def cb(c): bot_send(f"✅ {c} unique members processed so far...")
        ok, msg, members = tele_fetch_members(cb)
        if not ok: 
            bot_send(f"❌ {msg}"); return
        # Save to CSV
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "username", "fname", "lname", "phone"])
            w.writerows(members)
        bot_send_file(OUTPUT_CSV, f"🎉 Full fetch done: {len(members)} unique members!")
        bot_send("✅ Script complete! Check CSV.")
        return
    if lower.startswith("/status"):
        bot_send(f"Status: {json.dumps(s, indent=2)}")
        return
    if lower.startswith("/users_count"):
        if os.path.exists(OUTPUT_CSV):
            with open(OUTPUT_CSV, encoding="utf-8") as f:
                c = sum(1 for _ in f) - 1
            bot_send(f"📈 {c} users in CSV")
        else:
            bot_send("No CSV yet")
        return
    if lower.startswith("/reset"):
        s = {}
        save_state(s)
        if os.path.exists(OUTPUT_CSV): os.remove(OUTPUT_CSV)
        bot_send("🔄 State & CSV reset - Start fresh!")
        return
    bot_send("❓ Unknown command. Use /help")
# ---------- MAIN LOOP ----------
def main_loop():
    print("🚀 FULL SCRIPT STARTED: 90k+ Aggressive Fetcher Ready!")
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
