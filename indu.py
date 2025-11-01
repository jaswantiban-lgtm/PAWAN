import telebot
from telebot import types
import time
import requests
import json
import threading
import os
from datetime import datetime
import random
import string
import base64

# =============== CONFIG ===============
BOT_TOKEN = "7077920703:AAG2kLy0sJJbR3ZlouL7_5PewSWrEc-A1ik"
ADMIN_ID = 2054354957
INITIAL_LICENSE_KEY = "RINKI_KUSHWAHA"

# GitHub Sync Configuration
GITHUB_TOKEN = "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"  # Replace with your actual token
REPO_OWNER = "jaswantiban-lgtm"          # Replace with your GitHub username
REPO_NAME = "PAWAN"                 # Replace with your repository name
ENABLE_GITHUB_SYNC = True                    # Set to False to disable GitHub sync

# License key rotation settings - Now only manual rotation
CURRENT_LICENSE_KEY = INITIAL_LICENSE_KEY

# APIs
API_MOBILE = "http://dark-op.dev-is.xyz/?key=wasdark&number="
API_VEHICLE = "http://dark-op.dev-is.xyz/?key=wasdark&vehicle="
API_AADHAAR = "http://dark-op.dev-is.xyz/?key=wasdark&aadhaar="
API_UPI = "http://dark-op.dev-is.xyz/?key=wasdark&upi="

# Settings
SESSION_TIMEOUT = 1800
COOLDOWN_SECONDS = 10
FREE_SEARCHES = 10
WARNING_LIMIT = 5
TEMP_BAN_SECONDS = 600

# Bonus settings
DAILY_BONUS_MIN = 1
DAILY_BONUS_MAX = 2

# Data file
current_dir = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(current_dir, "data.json")

bot = telebot.TeleBot(BOT_TOKEN)

# =============== PERSISTENT DATA ===============
data_lock = threading.Lock()
default_data = {
    "user_searches": {}, "user_sessions": {}, "user_last_request": {},
    "user_warnings": {}, "user_bans": {}, "user_states": {}, "user_logs": {},
    "verified_users": {}, "last_bonus_claim": {}
}

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                d = json.load(f)
                for k in default_data:
                    if k not in d:
                        d[k] = default_data[k]
                print(f"✅ Data loaded from {DATA_FILE}")
                return d
        else:
            print(f"📁 Creating new data file: {DATA_FILE}")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
    
    return {k: v.copy() for k, v in default_data.items()}

# =============== GITHUB SYNC FUNCTIONS ===============
def sync_with_github(reason="manual"):
    """Sync data.json with GitHub repository"""
    if not ENABLE_GITHUB_SYNC:
        print("⚠️ GitHub sync is disabled")
        return False
        
    if not GITHUB_TOKEN or GITHUB_TOKEN == "ghp_your_github_token_here":
        print("⚠️ GitHub token not configured")
        return False
        
    try:
        # Read the current data file
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Encode to base64
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        # GitHub API URL
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/data.json"
        
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Get current file SHA
        response = requests.get(url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json().get('sha')
            print(f"📁 Found existing file on GitHub, SHA: {sha[:8]}...")
        elif response.status_code == 404:
            print("📁 Creating new file on GitHub...")
        else:
            print(f"❌ GitHub API error (get): {response.status_code} - {response.text}")
            return False
        
        # Prepare update data
        update_data = {
            "message": f"🤖 Bot Data Update: {reason} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": content_b64,
            "branch": "main"
        }
        
        if sha:
            update_data["sha"] = sha
        
        # Update file on GitHub
        response = requests.put(url, headers=headers, json=update_data)
        
        if response.status_code in [200, 201]:
            print("🎉 Data successfully synced with GitHub!")
            return True
        else:
            print(f"❌ GitHub sync failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ GitHub sync error: {e}")
        return False

def save_data(d=None, reason="auto"):
    global data
    if d is None:
        d = data
    
    try:
        with data_lock:
            with open(DATA_FILE, "w") as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
            print(f"💾 Data saved [{reason}] - Users: {len(d['user_searches'])}")
            
            # Auto-sync to GitHub for important events
            if ENABLE_GITHUB_SYNC and reason in ["admin_add", "license_rotation", "broadcast_complete", "daily_bonus"]:
                print("🔄 Auto-syncing with GitHub...")
                sync_with_github(f"auto_{reason}")
                
    except Exception as e:
        print(f"❌ Error saving data [{reason}]: {e}")

# Load data immediately
data = load_data()

# =============== LICENSE KEY MANAGEMENT ===============
def generate_new_license_key():
    new_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    print(f"🔄 Generated new license key: {new_key}")
    return new_key

def rotate_license_key(new_key=None):
    global CURRENT_LICENSE_KEY
    
    if new_key:
        # Use provided key
        old_key = CURRENT_LICENSE_KEY
        CURRENT_LICENSE_KEY = new_key
        print(f"✅ License key changed from {old_key} to {new_key}")
    else:
        # Generate random key
        old_key = CURRENT_LICENSE_KEY
        new_key = generate_new_license_key()
        CURRENT_LICENSE_KEY = new_key
        print(f"✅ License key rotated from {old_key} to {new_key}")
    
    # Clear all verified users since key changed
    data["verified_users"] = {}
    save_data(reason="license_rotation")
    
    return new_key

def is_user_verified(user_id):
    uid = str(user_id)
    return data["verified_users"].get(uid) == CURRENT_LICENSE_KEY

def verify_user(user_id):
    uid = str(user_id)
    data["verified_users"][uid] = CURRENT_LICENSE_KEY
    save_data(reason="user_verification")

def revoke_user_verification(user_id):
    """Revoke user verification (used when session expires)"""
    uid = str(user_id)
    if uid in data["verified_users"]:
        data["verified_users"].pop(uid, None)
        save_data(reason="revoke_verification")

# =============== DAILY BONUS FEATURE ===============
def can_claim_daily_bonus(user_id):
    """Check if user can claim daily bonus"""
    uid = str(user_id)
    last_claim = data["last_bonus_claim"].get(uid, 0)
    now = time.time()
    
    # Check if 24 hours have passed since last claim
    return (now - last_claim) >= 86400  # 24 hours in seconds

def claim_daily_bonus(user_id):
    """Give daily bonus to user"""
    uid = str(user_id)
    
    # Generate random bonus between 3-5 credits
    bonus_amount = random.randint(DAILY_BONUS_MIN, DAILY_BONUS_MAX)
    
    # Get current credits
    current_credits = data["user_searches"].get(uid, 0)
    
    # Add bonus to current credits
    new_credits = current_credits + bonus_amount
    data["user_searches"][uid] = new_credits
    
    # Update last claim time
    data["last_bonus_claim"][uid] = time.time()
    
    save_data(reason="daily_bonus")
    
    print(f"🎁 User {user_id} claimed {bonus_amount} daily bonus. New balance: {new_credits}")
    return bonus_amount, new_credits

def get_next_bonus_time(user_id):
    """Get time until next bonus is available"""
    uid = str(user_id)
    last_claim = data["last_bonus_claim"].get(uid, 0)
    if last_claim == 0:
        return 0  # Can claim immediately
    
    next_claim_time = last_claim + 86400  # 24 hours later
    now = time.time()
    
    if now >= next_claim_time:
        return 0  # Can claim now
    
    remaining = next_claim_time - now
    return int(remaining)

def format_time_remaining(seconds):
    """Format seconds into hours and minutes"""
    if seconds == 0:
        return "now"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

# =============== BROADCAST FEATURE ===============
def broadcast_message(message_text):
    """Send message to all users who have started the bot"""
    users = list(data["user_searches"].keys())
    success_count = 0
    fail_count = 0
    
    bot.send_message(ADMIN_ID, f"📢 Starting broadcast to {len(users)} users...")
    
    for user_id_str in users:
        try:
            user_id = int(user_id_str)
            bot.send_message(user_id, f"📢 Announcement:\n\n{message_text}")
            success_count += 1
            time.sleep(0.1)  # Small delay to avoid rate limits
        except Exception as e:
            print(f"❌ Failed to send to {user_id_str}: {e}")
            fail_count += 1
    
    return success_count, fail_count

# =============== UTILITIES ===============
def auto_save(reason="unknown"):
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            save_data(reason=f"{reason}_{func.__name__}")
            return result
        return wrapper
    return decorator

@auto_save(reason="log")
def log_user_activity(user_id, action, value=""):
    uid = str(user_id)
    entry = f"{datetime.utcnow().isoformat()} | {action} | {value}"
    data["user_logs"].setdefault(uid, []).append(entry)

@auto_save(reason="user")
def ensure_user(user_id):
    uid = str(user_id)
    changed = False
    if uid not in data["user_searches"]:
        data["user_searches"][uid] = FREE_SEARCHES
        changed = True
        print(f"👤 New user {uid} created with {FREE_SEARCHES} credits")
    if uid not in data["user_sessions"]:
        data["user_sessions"][uid] = 0
        changed = True
    if uid not in data["user_last_request"]:
        data["user_last_request"][uid] = 0
        changed = True
    if uid not in data["user_warnings"]:
        data["user_warnings"][uid] = 0
        changed = True
    return changed

def is_banned(user_id):
    uid = str(user_id)
    ban_until = data["user_bans"].get(uid, 0)
    now = time.time()
    if now < ban_until:
        return True, int(ban_until - now)
    if uid in data["user_bans"] and now >= ban_until:
        data["user_bans"].pop(uid, None)
        data["user_warnings"][uid] = 0
        save_data(reason="unban")
    return False, 0

@auto_save(reason="warning")
def add_warning(user_id, reason=""):
    uid = str(user_id)
    data["user_warnings"][uid] = data["user_warnings"].get(uid, 0) + 1
    warn_count = data["user_warnings"][uid]
    log_user_activity(user_id, "Warning", f"{warn_count} | {reason}")
    if warn_count >= WARNING_LIMIT:
        data["user_bans"][uid] = time.time() + TEMP_BAN_SECONDS
        bot.send_message(ADMIN_ID, f"⚠️ User {user_id} temporarily banned for abuse (warnings={warn_count}).")
        return True
    return False

@auto_save(reason="session")
def start_session(user_id):
    uid = str(user_id)
    data["user_sessions"][uid] = time.time()
    ensure_user(user_id)

@auto_save(reason="session")
def check_session(user_id):
    uid = str(user_id)
    last = data["user_sessions"].get(uid, 0)
    now = time.time()
    if now - last > SESSION_TIMEOUT:
        # Session expired - revoke verification
        revoke_user_verification(user_id)
        return False
    data["user_sessions"][uid] = now
    return True

def get_remaining_searches(user_id):
    return data["user_searches"].get(str(user_id), 0)

@auto_save(reason="search")
def decrease_search(user_id):
    uid = str(user_id)
    current_searches = data["user_searches"].get(uid, 0)
    if current_searches > 0:
        data["user_searches"][uid] = current_searches - 1
        print(f"🔍 User {uid} used 1 search. Remaining: {current_searches - 1}")
        return True
    return False

def validate_input(state, text):
    t = text.strip()
    if state == "mobile":
        return t.isdigit() and len(t) == 10
    if state == "aadhaar":
        return t.isdigit() and len(t) == 12
    if state == "vehicle":
        return len(t) >= 5
    if state == "upi":
        return ("@" in t) or t.isdigit()
    if state == "license":
        return len(t) > 0
    return False

def progress_steps():
    return ["🤚🏻 10%", "🤩 20%", "😎 30%", "😈 40%", "🎊 50%",
            "🥴 60%", "🤯 70%", "😁 80%", "☠️ 90%", "✅ 100%"]

# =============== KEYBOARD ===============
def main_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("📱 MOBILE", callback_data="mobile"),
        types.InlineKeyboardButton("💳 UPI", callback_data="upi"),
    )
    kb.row(
        types.InlineKeyboardButton("🚗 VEHICLE", callback_data="vehicle"),
        types.InlineKeyboardButton("🆔 AADHAAR", callback_data="aadhaar"),
    )
    kb.row(
        types.InlineKeyboardButton("🎁 DAILY BONUS", callback_data="daily_bonus"),
        types.InlineKeyboardButton("👤 ADMIN", url="https://t.me/jaswant_exe_bot")
    )
    return kb

# =============== HANDLERS ===============
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    chat_id = msg.chat.id
    uid = str(chat_id)
    
    # Always ensure user exists
    ensure_user(chat_id)
    
    # Check if session expired or user needs verification
    session_valid = check_session(chat_id)
    user_verified = is_user_verified(chat_id)
    
    if not session_valid or not user_verified:
        # Session expired OR not verified - ask for license key
        data["user_states"][uid] = "awaiting_license"
        save_data(reason="start_needs_verification")
        start_session(chat_id)
        current_credits = get_remaining_searches(chat_id)
        
        if not session_valid:
            print(f"🔄 User {chat_id} session expired - requiring re-verification. Credits: {current_credits}")
            bot.send_message(chat_id,
                           f"🔐 Session expired! Please enter your License Key to verify again.\n\nYou have {current_credits} searches available.")
        else:
            print(f"🚀 User {chat_id} started - needs verification. Credits: {current_credits}")
            bot.send_message(chat_id,
                           f"🔑 Please enter your License Key to verify.\n\nYou have {current_credits} searches available.")
    else:
        # Session valid and user verified - proceed directly
        start_session(chat_id)
        data["user_states"].pop(uid, None)
        save_data(reason="restart_verified")
        current_credits = get_remaining_searches(chat_id)
        
        # Check bonus status
        bonus_available = can_claim_daily_bonus(chat_id)
        if bonus_available:
            bonus_msg = "\n\n🎁 *Daily Bonus Available!* Click the 'DAILY BONUS' button to claim your free credits!"
        else:
            next_bonus = get_next_bonus_time(chat_id)
            if next_bonus > 0:
                time_left = format_time_remaining(next_bonus)
                bonus_msg = f"\n\n⏳ Next bonus available in: {time_left}"
            else:
                bonus_msg = "\n\n🎁 *Daily Bonus Available!* Click the 'DAILY BONUS' button!"
        
        print(f"🔁 User {chat_id} restarted - already verified. Credits: {current_credits}")
        bot.send_message(chat_id, f"✅ Welcome back!\nYou have {current_credits} searches left.{bonus_msg}", 
                        reply_markup=main_keyboard(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def inline_callback(call):
    chat_id = call.message.chat.id
    uid = str(chat_id)

    if not check_session(chat_id):
        bot.answer_callback_query(call.id, "⚠️ Session expired! Send /start to re-open.", show_alert=True)
        return

    # Check if user is verified
    if not is_user_verified(chat_id):
        bot.answer_callback_query(call.id, "🔒 Please verify your license first. Send /start", show_alert=True)
        return

    banned, remain = is_banned(chat_id)
    if banned:
        bot.answer_callback_query(call.id, f"🚫 Temporarily banned. Try after {remain}s.", show_alert=True)
        return

    if call.data == "daily_bonus":
        # Handle daily bonus claim
        if can_claim_daily_bonus(chat_id):
            bonus_amount, new_balance = claim_daily_bonus(chat_id)
            
            # Create celebration message
            celebration_emojis = ["🎉", "🎊", "🎁", "💰", "💎", "✨"]
            celebration = random.choice(celebration_emojis)
            
            bonus_msg = f"""{celebration} *DAILY BONUS CLAIMED!* {celebration}

🎁 You received: *{bonus_amount} credits*
💰 Your new balance: *{new_balance} credits*

Come back tomorrow for more free credits! 🕐"""
            
            bot.send_message(chat_id, bonus_msg, parse_mode="Markdown")
            bot.answer_callback_query(call.id, f"🎁 You got {bonus_amount} credits! New balance: {new_balance}")
            
            # Update the message with new balance
            try:
                next_bonus = get_next_bonus_time(chat_id)
                time_left = format_time_remaining(next_bonus)
                bonus_status = f"\n\n⏳ Next bonus available in: {time_left}"
                
                bot.edit_message_text(
                    f"✅ Welcome back!\nYou have {new_balance} searches left.{bonus_status}",
                    chat_id,
                    call.message.message_id,
                    reply_markup=main_keyboard()
                )
            except Exception as e:
                print(f"⚠️ Could not update message: {e}")
                
        else:
            next_bonus = get_next_bonus_time(chat_id)
            time_left = format_time_remaining(next_bonus)
            bot.answer_callback_query(call.id, f"⏳ Come back in {time_left} for your next bonus!", show_alert=True)
        return

    # Handle search type selections
    data["user_states"][uid] = call.data
    save_data(reason="inline_click")
    
    response_msg = f"🔍 Please enter the {call.data} value now:"
    bot.send_message(chat_id, response_msg)
    
    bot.answer_callback_query(call.id, f"Selected: {call.data}")

@bot.message_handler(func=lambda m: True)
def handle_message(m):
    chat_id = m.chat.id
    text = m.text.strip() if m.text else ""
    uid = str(chat_id)

    # Admin commands
    if text.startswith("/") and chat_id == ADMIN_ID:
        parts = text.split()
        cmd = parts[0].lower()
        
        if cmd == "/add":
            try:
                target = int(parts[1])
                amount = int(parts[2])
                t_uid = str(target)
                
                current_credits = data["user_searches"].get(t_uid, 0)
                new_credits = current_credits + amount
                data["user_searches"][t_uid] = new_credits
                save_data(reason="admin_add")
                
                print(f"➕ Admin added {amount} credits to user {target}. Total: {new_credits}")
                bot.send_message(ADMIN_ID, f"✅ Added {amount} searches to user {target}. Total: {new_credits}")
                bot.send_message(target, f"🎁 Admin added {amount} searches to your account. Now you have {new_credits} searches.")
            except Exception as e:
                print(f"❌ Error in /add command: {e}")
                bot.send_message(ADMIN_ID, "Usage: /add <user_id> <count>")
            return
        
        elif cmd == "/log":
            lines = []
            for k, v in data["user_searches"].items():
                lines.append(f"User {k} → {v} searches")
            text_out = "\n".join(lines) if lines else "No users yet."
            bot.send_message(ADMIN_ID, f"📋 Users:\n\n{text_out}")
            return
        
        elif cmd == "/unban":
            try:
                target = str(int(parts[1]))
                if target in data["user_bans"]:
                    data["user_bans"].pop(target, None)
                data["user_warnings"][target] = 0
                save_data(reason="admin_unban")
                bot.send_message(ADMIN_ID, f"✅ Unbanned {target}")
                bot.send_message(int(target), "✅ You have been unbanned by admin. Please /start to continue.")
            except Exception:
                bot.send_message(ADMIN_ID, "Usage: /unban <user_id>")
            return
        
        elif cmd == "/newkey":
            if len(parts) == 2:
                # Manual key provided: /newkey xxxxxx
                new_key = parts[1]
                if len(new_key) >= 4:  # Minimum key length
                    rotated_key = rotate_license_key(new_key)
                    bot.send_message(ADMIN_ID, f"✅ License key changed to: {rotated_key}")
                else:
                    bot.send_message(ADMIN_ID, "❌ Key must be at least 4 characters long.")
            else:
                # Auto-generate key: /newkey
                rotated_key = rotate_license_key()
                bot.send_message(ADMIN_ID, f"✅ License key rotated to: {rotated_key}")
            return
        
        elif cmd == "/currentkey":
            bot.send_message(ADMIN_ID, f"🔑 Current License Key: {CURRENT_LICENSE_KEY}")
            return
        
        elif cmd == "/broadcast":
            if len(parts) >= 2:
                message_text = ' '.join(parts[1:])
                bot.send_message(ADMIN_ID, f"📢 Preparing to broadcast:\n\n{message_text}\n\nConfirm? (yes/no)")
                data["user_states"][uid] = "awaiting_broadcast_confirmation"
                data["broadcast_message"] = message_text
                save_data(reason="broadcast_init")
            else:
                bot.send_message(ADMIN_ID, "Usage: /broadcast <message>")
            return
        
        elif cmd == "/stats":
            total_users = len(data["user_searches"])
            active_users = len([uid for uid in data["user_sessions"] if time.time() - data["user_sessions"].get(uid, 0) < 86400])
            total_searches = sum(data["user_searches"].values())
            verified_users = len(data["verified_users"])
            bonus_claims_today = len([uid for uid, last_claim in data["last_bonus_claim"].items() 
                                    if time.time() - last_claim < 86400])
            
            stats_msg = f"""📊 Bot Statistics:
            
👥 Total Users: {total_users}
✅ Verified Users: {verified_users}
🔍 Active Users (24h): {active_users}
💫 Total Search Credits: {total_searches}
🎁 Bonus Claims Today: {bonus_claims_today}
🔑 Current License Key: {CURRENT_LICENSE_KEY}
🔄 GitHub Sync: {'ENABLED' if ENABLE_GITHUB_SYNC else 'DISABLED'}"""
            
            bot.send_message(ADMIN_ID, stats_msg)
            return

        elif cmd == "/sync":
            """Manual GitHub sync command"""
            bot.send_message(ADMIN_ID, "🔄 Syncing data with GitHub...")
            if sync_with_github("manual_sync"):
                bot.send_message(ADMIN_ID, "✅ Successfully synced data with GitHub!")
            else:
                bot.send_message(ADMIN_ID, "❌ Failed to sync with GitHub. Check console for details.")
            return

        elif cmd == "/github_status":
            """Check GitHub sync status"""
            status_msg = f"""🔧 GitHub Sync Status:
            
📁 Repository: {REPO_OWNER}/{REPO_NAME}
🔄 Auto-Sync: {'ENABLED' if ENABLE_GITHUB_SYNC else 'DISABLED'}
🔑 Token Configured: {'YES' if GITHUB_TOKEN and GITHUB_TOKEN != "ghp_your_github_token_here" else 'NO'}
💾 Data File: {DATA_FILE}
👥 Local Users: {len(data['user_searches'])}"""

            bot.send_message(ADMIN_ID, status_msg)
            return

    # Handle broadcast confirmation
    if data["user_states"].get(uid) == "awaiting_broadcast_confirmation" and chat_id == ADMIN_ID:
        if text.lower() in ["yes", "y", "confirm"]:
            message_text = data.get("broadcast_message", "")
            if message_text:
                bot.send_message(ADMIN_ID, "🔄 Starting broadcast... This may take a while.")
                success, failed = broadcast_message(message_text)
                bot.send_message(ADMIN_ID, f"✅ Broadcast completed!\n\n✅ Success: {success}\n❌ Failed: {failed}")
            else:
                bot.send_message(ADMIN_ID, "❌ No broadcast message found.")
        else:
            bot.send_message(ADMIN_ID, "❌ Broadcast cancelled.")
        
        data["user_states"].pop(uid, None)
        if "broadcast_message" in data:
            data.pop("broadcast_message")
        save_data(reason="broadcast_complete")
        return

    if data["user_states"].get(uid) == "awaiting_license":
        if text == CURRENT_LICENSE_KEY:
            start_session(chat_id)
            verify_user(chat_id)
            data["user_states"].pop(uid, None)
            save_data(reason="license_verified")
            current_credits = get_remaining_searches(chat_id)
            print(f"✅ User {chat_id} verified license. Credits: {current_credits}")
            
            # Check bonus status for new verified user
            bonus_available = can_claim_daily_bonus(chat_id)
            if bonus_available:
                bonus_msg = "\n\n🎁 *Daily Bonus Available!* Click the 'DAILY BONUS' button to claim your free credits!"
            else:
                next_bonus = get_next_bonus_time(chat_id)
                if next_bonus > 0:
                    time_left = format_time_remaining(next_bonus)
                    bonus_msg = f"\n\n⏳ Next bonus available in: {time_left}"
                else:
                    bonus_msg = "\n\n🎁 *Daily Bonus Available!* Click the 'DAILY BONUS' button!"
            
            bot.send_message(chat_id, f"✅ License verified!\nYou have {current_credits} searches left.{bonus_msg}", 
                            reply_markup=main_keyboard(), parse_mode="Markdown")
            log_user_activity(chat_id, "LicenseVerified", "")
        else:
            bot.send_message(chat_id, "❌ Invalid license key. Please enter the current valid key.")
            log_user_activity(chat_id, "InvalidLicenseAttempt", text)
        return

    # Check if user is verified before allowing any features
    if not is_user_verified(chat_id):
        bot.send_message(chat_id, "🔒 Please verify your license key first. Send /start to begin verification.")
        return

    if text == "/start":
        # This handles the case when user is already verified but sends /start again
        start_session(chat_id)
        data["user_states"].pop(uid, None)
        save_data(reason="restart")
        current_credits = get_remaining_searches(chat_id)
        print(f"🔁 User {chat_id} restarted. Credits: {current_credits}")
        
        # Check bonus status
        bonus_available = can_claim_daily_bonus(chat_id)
        if bonus_available:
            bonus_msg = "\n\n🎁 *Daily Bonus Available!* Click the 'DAILY BONUS' button to claim your free credits!"
        else:
            next_bonus = get_next_bonus_time(chat_id)
            if next_bonus > 0:
                time_left = format_time_remaining(next_bonus)
                bonus_msg = f"\n\n⏳ Next bonus available in: {time_left}"
            else:
                bonus_msg = "\n\n🎁 *Daily Bonus Available!* Click the 'DAILY BONUS' button!"
        
        bot.send_message(chat_id, f"🔁 Session refreshed. You have {current_credits} searches.{bonus_msg}", 
                        reply_markup=main_keyboard(), parse_mode="Markdown")
        log_user_activity(chat_id, "StartCommand", "")
        return

    banned, remain = is_banned(chat_id)
    if banned:
        bot.send_message(chat_id, f"🚫 You are temporarily banned for abuse.\nTry again after {remain} seconds.")
        return

    cur_state = data["user_states"].get(uid)
    if cur_state in ["mobile", "aadhaar", "vehicle", "upi"]:
        if not check_session(chat_id):
            bot.send_message(chat_id, "⚠️ Session expired! Please send /start again to continue.")
            data["user_states"].pop(uid, None)
            save_data(reason="session_expired")
            return

        last_req = data["user_last_request"].get(uid, 0)
        now = time.time()
        if now - last_req < COOLDOWN_SECONDS:
            blocked = add_warning(chat_id, "Cooldown violation")
            if blocked:
                bot.send_message(chat_id, "🚫 You have been temporarily banned for repeated abuse.")
            else:
                wait = int(COOLDOWN_SECONDS - (now - last_req))
                bot.send_message(chat_id, f"⚠️ Please wait {wait} seconds before the next search.")
            return

        if not validate_input(cur_state, text):
            bot.send_message(chat_id, "❌ Invalid input format for this search type. Try again.")
            add_warning(chat_id, "Invalid input format")
            return

        ensure_user(chat_id)
        current_credits = get_remaining_searches(chat_id)
        if current_credits <= 0:
            bot.send_message(chat_id, "⚠️ You have used all your free searches. Click 'Buy Search' to get more.")
            bot.send_message(chat_id, "💰 Buy Here: https://t.me/jaswant_exe_bot")
            return

        data["user_last_request"][uid] = now
        data["user_sessions"][uid] = now
        save_data(reason="search_start")

        progress = progress_steps()
        m = bot.send_message(chat_id, f"⏳ {cur_state.capitalize()} Lookup...\n{progress[0]}")
        try:
            for step in progress[1:]:
                time.sleep(0.45)
                bot.edit_message_text(f"⏳ {cur_state.capitalize()} Lookup...\n{step}", chat_id, m.message_id)
        except Exception:
            pass

        try:
            if cur_state == "mobile":
                url = API_MOBILE + text
            elif cur_state == "aadhaar":
                url = API_AADHAAR + text
            elif cur_state == "vehicle":
                url = API_VEHICLE + text
            elif cur_state == "upi":
                url = API_UPI + text
            else:
                url = None

            res_text = "❌ No data found or service temporarily unavailable"
            if url:
                rsp = requests.get(url, timeout=15)
                if rsp.status_code == 200:
                    res_text = rsp.text
                    if not res_text.strip() or "error" in res_text.lower():
                        res_text = "❌ No data found for this query"
                else:
                    res_text = "❌ Service temporarily unavailable. Please try again later."
        except requests.exceptions.Timeout:
            res_text = "❌ Request timeout. Please try again later."
        except requests.exceptions.ConnectionError:
            res_text = "❌ Connection error. Please check your internet and try again."
        except Exception:
            res_text = "❌ Service temporarily unavailable. Please try again later."

        try:
            if url and 'rsp' in locals() and rsp.status_code == 200 and "❌" not in res_text:
                decrease_search(chat_id)
        except Exception:
            pass

        remaining = get_remaining_searches(chat_id)
        instagram_link = "<a href='https://instagram.com/jaswant.exe'>✨ FOLLOW ME ❤️</a>"
        formatted = f"<b>{cur_state.capitalize()} Result</b>\n\n<pre>{res_text}</pre>\n\n🔍 Remaining Searches: {remaining}\n\n{instagram_link}"
        bot.send_message(chat_id, formatted, parse_mode="HTML")
        log_user_activity(chat_id, "Search", f"{cur_state} | query={text} | remaining={remaining}")

        data["user_states"].pop(uid, None)
        save_data(reason="search_complete")
        return

    if text.lower() in ["mobile", "aadhaar", "vehicle", "upi"]:
        if not check_session(chat_id):
            bot.send_message(chat_id, "⚠️ Session expired! Please send /start again to continue.")
            return
        
        # Double-check verification
        if not is_user_verified(chat_id):
            bot.send_message(chat_id, "🔒 Your verification has expired. Please send /start to verify again.")
            return
            
        data["user_states"][uid] = text.lower()
        save_data(reason="search_type")
        bot.send_message(chat_id, f"🔍 Enter the {text} value now:")
        log_user_activity(chat_id, "StartSearchType", text.lower())
        return

    bot.send_message(chat_id, "🤖 Command not recognized. Use /start to start the bot.")
    return

def periodic_save():
    """Periodic backup save"""
    while True:
        time.sleep(30)
        save_data(reason="periodic_backup")
        print("💾 Periodic backup save completed")

def periodic_github_sync():
    """Automatically sync with GitHub every hour"""
    while True:
        time.sleep(3600)  # 1 hour
        if ENABLE_GITHUB_SYNC and GITHUB_TOKEN and GITHUB_TOKEN != "ghp_your_github_token_here":
            print("🔄 Auto-syncing with GitHub...")
            if sync_with_github("auto_sync"):
                print("✅ Auto-sync completed")
            else:
                print("❌ Auto-sync failed")

# Start background threads
t1 = threading.Thread(target=periodic_save, daemon=True)
t1.start()

t2 = threading.Thread(target=periodic_github_sync, daemon=True)
t2.start()

# =============== BOT START ===============
def start_bot_with_retry():
    max_retries = 5
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            print(f"🤖 Attempting to start bot... (Attempt {attempt + 1}/{max_retries})")
            print(f"🔑 Current License Key: {CURRENT_LICENSE_KEY}")
            print(f"⏰ Session timeout: {SESSION_TIMEOUT} seconds")
            print(f"🎁 Daily Bonus: {DAILY_BONUS_MIN}-{DAILY_BONUS_MAX} credits")
            print(f"🔄 GitHub Sync: {'ENABLED' if ENABLE_GITHUB_SYNC else 'DISABLED'}")
            
            test_conn = requests.get("https://api.telegram.org", timeout=10)
            print("✅ Connected to Telegram API")
            
            # Initial GitHub sync
            if ENABLE_GITHUB_SYNC and GITHUB_TOKEN and GITHUB_TOKEN != "ghp_your_github_token_here":
                print("🔄 Performing initial GitHub sync...")
                sync_with_github("initial_sync")
            
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
            
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Network error (Attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print("🚫 Max retries exceeded. Please check your internet connection.")
                break
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
            break

print("=" * 50)
print("🤖 BOT STARTING...")
print("=" * 50)
print(f"📁 Data file: {DATA_FILE}")
print(f"💫 Auto-save: ACTIVE")
print(f"🔐 Session verification: ACTIVE")
print(f"📢 Broadcast feature: ENABLED")
print(f"🎁 Daily Bonus: ENABLED")
print(f"🔄 GitHub Sync: {'ENABLED' if ENABLE_GITHUB_SYNC else 'DISABLED'}")
print("=" * 50)
start_bot_with_retry()
