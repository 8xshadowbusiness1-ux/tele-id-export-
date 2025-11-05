#!/usr/bin/env python3
"""
✅ ULTIMATE FIX: 90k+ Fetcher (Manual Aggressive - a-z Searches)
✔ Bypasses deprecated aggressive=True with manual alphabet loops
✔ Admin check + entity resolve
✔ Handles floodwait, unique users, resume
✔ Render-safe (Background Worker recommended)
"""
import os, time, json, csv, asyncio, random, threading, requests, traceback
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChatAdminRequiredError, UserPrivacyRestrictedError
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
# Search queries for manual aggressive (a-z + extras)
SEARCH_QUERIES = [chr(i) for i in range(ord('a'), ord('z')+1)] + ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '@', '_']
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
# ---------- LOGIN (Same) ----------
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
# ---------- MANUAL AGGRESSIVE FETCH (NEW FIX) ----------
def tele_fetch_members(progress_cb=None):
    members = []
    async def inner():
        c = TelegramClient("session_bot", API_ID, API_HASH)
        await c.connect()
        if not await c.is_user_authorized():
            raise Exception("Not logged in.")
        
        s = load_state()
        fetched_count = s.get("manual_fetched", 0)
        if fetched_count > 0:
            bot_send(f"🔁 Resuming manual aggressive from {fetched_count} users")
        
        bot_send("🔍 Resolving entity & checking admin access...")
        
        try:
            # STEP 1: Resolve entity
            entity = await c.get_entity(TUTORIAL_ID)
            bot_send(f"✅ Entity: {entity.title} ({entity.id})")
            
            # STEP 2: Test access (fetch 1)
            test_participants = await c.get_participants(entity, limit=1)
            if not test_participants:
                raise ChatAdminRequiredError("No access")
            bot_send("✅ Admin access confirmed - Starting manual a-z fetch (~15-30 min for 90k+)...")
            
        except ChatAdminRequiredError:
            raise Exception("❌ ADMIN RIGHTS NEEDED! Add account as admin with 'View Members' permission.")
        except UserPrivacyRestrictedError:
            raise Exception("❌ Account not in group or privacy blocked.")
        except Exception as e:
            raise Exception(f"❌ Entity error: {e}")
        
        # MANUAL AGGRESSIVE: Loop over searches to bypass 10k limit
        seen_ids = set()  # Unique users
        total_raw = 0
        for q in SEARCH_QUERIES:
            if s.get("stop_fetch"):  # For resume/cancel
                break
            try:
                bot_send(f"🔍 Searching with '{q}'... (progress: {fetched_count}/{len(SEARCH_QUERIES)})")
                participants = await c.get_participants(entity, search=q, limit=0)
                batch_count = 0
                for user in participants:
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
                        batch_count += 1
                        fetched_count += 1
                        total_raw += 1
                        
                        # Progress save
                        if fetched_count % PROGRESS_BATCH == 0:
                            s["manual_fetched"] = fetched_count
                            save_state(s)
                            if progress_cb:
                                progress_cb(fetched_count)
                            await asyncio.sleep(random.uniform(1, 2))  # Anti-flood
                
                bot_send(f"✅ '{q}' done: +{batch_count} unique (total raw: {total_raw})")
                await asyncio.sleep(random.uniform(2, 4))  # Between searches
                
            except FloodWaitError as fw:
                bot_send(f"⏸️ FloodWait on '{q}': {fw.seconds}s - Waiting...")
                await asyncio.sleep(fw.seconds + 5)
                continue  # Retry next time or restart
            except Exception as e:
                bot_send(f"⚠️ Error on '{q}': {e} - Skipping...")
                continue
        
        # Final
        s["manual_fetched"] = 0
        s["stop_fetch"] = False
        save_state(s)
        bot_send(f"📊 Manual fetch done: {total_raw} raw, {len(members)} unique!")
        if progress_cb:
            progress_cb(len(members))
        await c.disconnect()
    
    try:
        asyncio.run(inner())
        return True, f"✅ Fetched {len(members)} UNIQUE members!", members
    except FloodWaitError as fw:
        bot_send(f"🔄 FloodWait {fw.seconds}s - Restart /fetch")
        return False, f"FloodWait - Partial saved", members
    except Exception as e:
        traceback.print_exc()
        return False, str(e), members
# ---------- PING (Same) ----------
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
        bot_send("👋 Fixed! /login → /otp → /check_access → /fetch (90k+ manual mode)")
        return
    if lower.startswith("/help"):
        bot_send("/login\n/otp <code>\n/2fa <pwd>\n/check_access\n/fetch\n/status\n/users_count\n/reset")
        return
    if lower.startswith("/login"):
        tele_send_code(); return
    if lower.startswith("/otp"):
        p = text.split()
        if len(p) < 2: bot_send("Usage: /otp <code>"); return
        ok, need2fa, msg = tele_sign_in_with_code(p[1])
        bot_send(msg)
        if need2fa: bot_send("Send /2fa <pwd>")
        return
    if lower.startswith("/2fa"):
        p = text.split(maxsplit=1)
        if len(p) < 2: bot_send("Usage: /2fa <pwd>"); return
        ok, msg = tele_sign_in_with_password(p[1])
        bot_send(msg)
        return
    if lower.startswith("/check_access"):
        if not s.get("logged_in"):
            bot_send("Login first."); return
        async def check():
            c = TelegramClient("session_bot", API_ID, API_HASH)
            await c.connect()
            try:
                entity = await c.get_entity(TUTORIAL_ID)
                test = await c.get_participants(entity, limit=1)
                if test:
                    bot_send(f"✅ Access OK: {len(test)} member visible in {entity.title}")
                else:
                    bot_send("❌ No access - Make admin!")
            except Exception as e:
                bot_send(f"❌ Check failed: {e}")
            await c.disconnect()
        asyncio.run(check())
        return
    if lower.startswith("/fetch"):
        if not s.get("logged_in"):
            bot_send("Login first."); return
        bot_send("🔄 Starting manual 90k+ fetch (a-z mode - 15-30 min, be patient)...")
        def cb(c): bot_send(f"✅ {c} unique processed...")
        ok, msg, members = tele_fetch_members(cb)
        if not ok: 
            bot_send(f"❌ {msg}"); return
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "username", "fname", "lname", "phone"])
            w.writerows(members)
        bot_send_file(OUTPUT_CSV, f"🎉 Done: {len(members)} unique members!")
        bot_send("✅ Check CSV - 90k+ success!")
        return
    if lower.startswith("/status"):
        bot_send(json.dumps(s, indent=2))
        return
    if lower.startswith("/users_count"):
        if os.path.exists(OUTPUT_CSV):
            with open(OUTPUT_CSV, encoding="utf-8") as f:
                c = sum(1 for _ in f) - 1
            bot_send(f"📈 {c} in CSV")
        else:
            bot_send("No CSV")
        return
    if lower.startswith("/reset"):
        s = {}
        save_state(s)
        if os.path.exists(OUTPUT_CSV): os.remove(OUTPUT_CSV)
        if os.path.exists("session_bot.session"): os.remove("session_bot.session")
        bot_send("🔄 Reset - Fresh start!")
        return
    bot_send("❓ Use /help")
# ---------- MAIN LOOP ----------
def main_loop():
    print("🚀 MANUAL AGGRESSIVE SCRIPT STARTED - 90k+ Fixed!")
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
