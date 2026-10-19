import logging
import sqlite3
import asyncio
import re
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from telethon import TelegramClient, functions
from telethon.errors import UserAlreadyParticipantError
from telethon.sessions import StringSession

# Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config Variables
BOT_TOKEN = "8825997856:AAE-pGk3aoNv437yPGWWNGUy8Xy6ruDilRM"
API_ID = 33756268  # Replace with your Telegram API ID
API_HASH = "aea24fa5ab912a74673c0302a0708227"  # Replace with your Telegram API Hash
OWNER_ID = 8222742232  # Bot Main Owner Numeric ID

# Conversation States
WAITING_STRING_SESSION = 1
WAITING_ADMIN_ID = 2
WAITING_JOIN_LINK = 3
WAITING_JOIN_COUNT = 4
WAITING_JOIN_DELAY = 5
WAITING_LEAVE_LINK = 6
WAITING_LEAVE_COUNT = 7

# Reaction States
WAITING_REACT_CHAN_LINK = 8
WAITING_REACT_POST_LINK = 9
WAITING_REACT_COUNT = 10
WAITING_REACT_DELAY = 11
WAITING_REACT_MODE_SELECT = 12
WAITING_REACT_SINGLE_EMOJI = 13
WAITING_REACT_MULTI_EMOJI = 14

# Buttons Setup
BTN_JOIN = "🚀 𝗝𝗢𝗜𝗡 𝗖𝗛𝗔𝗡𝗡𝗘𝗟/𝗚𝗥𝗢𝗨𝗣"
BTN_LEAVE = "🚪 𝗟𝗘𝗔𝗩𝗘 𝗖𝗛𝗔𝗡𝗡𝗘𝗟"
BTN_REACTION = "🎭 𝗥𝗘𝗔𝗖𝗧𝗜𝗢𝗡"
BTN_ADD_ACC = "➕ 𝗔𝗗𝗗 𝗔𝗖𝗖𝗢𝗨𝗡𝗧"
BTN_REM_ACC = "➖ 𝗥𝗘𝗠𝗢𝗩𝗘 𝗔𝗖𝗖𝗢𝗨𝗡𝗧"
BTN_LIST_ADM = "📋 𝗔𝗟𝗟 𝗔𝗗𝗠𝗜𝗡 𝗟𝗜𝗦𝗧"
BTN_ADD_ADM = "👑 𝗔𝗗𝗗 𝗔𝗗𝗠𝗜𝗡"
BTN_REM_ADM = "❌ 𝗥𝗘𝗠𝗢𝗩𝗘 𝗔𝗗𝗠𝗜𝗡"

ALL_MENU_BUTTONS = [BTN_JOIN, BTN_LEAVE, BTN_REACTION, BTN_ADD_ACC, BTN_REM_ACC, BTN_LIST_ADM, BTN_ADD_ADM, BTN_REM_ADM]
MENU_BUTTON_FILTER = filters.Regex(f"^({'|'.join([re.escape(b) for b in ALL_MENU_BUTTONS])})$")

# Database Setup
def init_db():
    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            first_name TEXT,
            username TEXT,
            string_session TEXT UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Check Authorization
def is_authorized(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

# Keyboard Menu Layout
def get_main_keyboard(user_id: int):
    if user_id == OWNER_ID:
        keyboard = [
            [BTN_JOIN, BTN_LEAVE],
            [BTN_REACTION],
            [BTN_ADD_ACC, BTN_REM_ACC],
            [BTN_LIST_ADM],
            [BTN_ADD_ADM, BTN_REM_ADM]
        ]
    else:
        keyboard = [
            [BTN_JOIN, BTN_LEAVE],
            [BTN_REACTION],
            [BTN_ADD_ACC, BTN_REM_ACC],
            [BTN_LIST_ADM]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Helper function to extract msg_id from post link
def parse_post_link(link: str):
    match = re.search(r'/(\d+)$', link)
    if match:
        return int(match.group(1))
    return None

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Aap is bot ke authorized user nahi hain.")
        return ConversationHandler.END

    role_str = "Owner 👑" if user_id == OWNER_ID else "Admin ⚡"
    await update.message.reply_text(
        f"👋 **Welcome {role_str}!**\n\nSystem active hai. Niche menu se koi bhi option chuniye:",
        reply_markup=get_main_keyboard(user_id),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ----------------- BUTTON 1: ADD ACCOUNT -----------------
async def add_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return ConversationHandler.END

    await update.message.reply_text(
        "📥 **Send String Session:**\n\nKripya apna Pyrogram ya Telethon String Session bhejiyen:",
        parse_mode="Markdown"
    )
    return WAITING_STRING_SESSION

async def receive_string_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session_str = update.message.text.strip()
    
    if session_str.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    status_msg = await update.message.reply_text("⏳ String session verify ho raha hai...")

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await status_msg.edit_text("❌ Ye String Session invalid/expired hai. Kripya sahi session bhejiyen:")
            await client.disconnect()
            return WAITING_STRING_SESSION

        me = await client.get_me()
        acc_id = me.id
        first_name = me.first_name or "Unknown"
        username = me.username or "None"
        await client.disconnect()

        conn = sqlite3.connect('accounts.db')
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO accounts (user_id, first_name, username, string_session) VALUES (?, ?, ?, ?)",
                (acc_id, first_name, username, session_str)
            )
            conn.commit()
            await status_msg.edit_text(
                f"🎉 **Account Added Successfully!**\n\n"
                f"👤 **Name:** {first_name}\n"
                f"🆔 **ID:** `{acc_id}`\n"
                f"🔗 **Username:** @{username}",
                parse_mode="Markdown"
            )
        except sqlite3.IntegrityError:
            await status_msg.edit_text("⚠️ Ye Account pehle se added hai!")
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error session: {e}")
        await status_msg.edit_text("❌ Galat String Session format hai. Kripya sahi Session code bhejiyen:")
        return WAITING_STRING_SESSION

    return ConversationHandler.END

# ----------------- BUTTON 2: REMOVE ACCOUNT -----------------
async def remove_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return ConversationHandler.END

    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, first_name FROM accounts")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("❌ Remove karne ke liye koi account available nahi hai.")
        return ConversationHandler.END

    keyboard = []
    for idx, row in enumerate(rows, start=1):
        db_id, acc_id, first_name = row
        keyboard.append([InlineKeyboardButton(f"📛 {idx}. {first_name} (ID: {acc_id})", callback_data=f"ask_rem_acc_{db_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("⚙️ Jis account ko remove karna hai us par click karein:", reply_markup=reply_markup)
    return ConversationHandler.END

# ----------------- BUTTON 3: JOIN CHANNEL/GROUP -----------------
async def join_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return ConversationHandler.END

    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM accounts")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        await update.message.reply_text(f"⚠️ Filhal bot me koi account added nahi hai. Pehle '{BTN_ADD_ACC}' par click karke account add karein.")
        return ConversationHandler.END

    context.user_data['total_accounts'] = count

    await update.message.reply_text(
        "📢 **Enter Channel / Group Link:**\n\n"
        "• Public Link: `https://t.me/yourchannel` ya `@yourchannel`\n"
        "• Private Link: `https://t.me/+abcdef...` ya `https://t.me/joinchat/...`",
        parse_mode="Markdown"
    )
    return WAITING_JOIN_LINK

async def receive_join_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    
    if link.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(update.effective_user.id))
        return ConversationHandler.END

    if not (link.startswith("https://t.me/") or link.startswith("t.me/") or link.startswith("@")):
        await update.message.reply_text(
            "❌ **Ye koi valid Telegram Link nahi hai!**\n\n"
            "Kripya sahi link bhejiyen (e.g. `https://t.me/...` ya `@channelname`):",
            parse_mode="Markdown"
        )
        return WAITING_JOIN_LINK

    context.user_data['target_link'] = link
    total = context.user_data.get('total_accounts', 1)

    await update.message.reply_text(
        f"📊 Bot ke paas total **{total}** accounts hain.\n\n"
        f"Aap kitne accounts ko join/join request karwana chahte hain? (1 se {total} tak number bhejiyen):",
        parse_mode="Markdown"
    )
    return WAITING_JOIN_COUNT

async def receive_join_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(update.effective_user.id))
        return ConversationHandler.END

    if not text.isdigit():
        await update.message.reply_text("❌ Galat input! Kripya sirf ek sahi number bhejiyen (e.g. 1, 5):")
        return WAITING_JOIN_COUNT

    count = int(text)
    total = context.user_data.get('total_accounts', 1)

    if count <= 0 or count > total:
        await update.message.reply_text(f"❌ Kripya 1 se {total} ke beech ka valid number darj karein:")
        return WAITING_JOIN_COUNT

    context.user_data['join_count'] = count

    await update.message.reply_text(
        "⏱ **Delay Setting:**\n\n"
        "Har account ke join karne ke beech kitne **Seconds** ka delay/interval hona chahiye? (e.g. `2` ya `5`):",
        parse_mode="Markdown"
    )
    return WAITING_JOIN_DELAY

async def receive_join_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    if not text.isdigit():
        await update.message.reply_text("❌ Galat input! Kripya numeric seconds bhejiyen (e.g. 2, 5):")
        return WAITING_JOIN_DELAY

    delay = int(text)
    target_link = context.user_data.get('target_link')
    join_count = context.user_data.get('join_count')

    await update.message.reply_text(
        f"✅ **Order Successfully Accepted!**\n\n"
        f"🔗 **Link:** {target_link}\n"
        f"👥 **Accounts:** {join_count}\n"
        f"⏱ **Delay:** {delay} Seconds\n\n"
        f"🔄 Joining process chalu ho raha hai...",
        parse_mode="Markdown"
    )

    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT first_name, username, string_session FROM accounts LIMIT ?", (join_count,))
    accounts = cursor.fetchall()
    conn.close()

    already_joined_count = 0
    newly_joined_count = 0
    failed_count = 0

    for idx, acc in enumerate(accounts, start=1):
        await asyncio.sleep(delay)

        first_name, username, session_str = acc
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()

            if "+" in target_link or "joinchat" in target_link:
                hash_match = re.search(r'(?:\+|\/joinchat\/)([a-zA-Z0-9_-]+)', target_link)
                if hash_match:
                    invite_hash = hash_match.group(1)
                    await client(functions.messages.ImportChatInviteRequest(hash=invite_hash))
                else:
                    await client(functions.messages.ImportChatInviteRequest(hash=target_link))
            else:
                clean_link = target_link.split("/")[-1].replace("@", "")
                await client(functions.channels.JoinChannelRequest(channel=clean_link))

            await client.disconnect()
            newly_joined_count += 1
            logger.info(f"Account {first_name} joined successfully.")

        except UserAlreadyParticipantError:
            already_joined_count += 1
            logger.info(f"Account {first_name} was already joined.")
            try:
                await client.disconnect()
            except Exception:
                pass

        except Exception as e:
            err_msg = str(e).lower()
            if "already" in err_msg or "user_already_participant" in err_msg:
                already_joined_count += 1
            else:
                logger.error(f"Error joining for {first_name}: {e}")
                failed_count += 1
            try:
                await client.disconnect()
            except Exception:
                pass

    total_successful_joined = already_joined_count + newly_joined_count

    report_text = (
        f"🎉 **Process Completed!**\n\n"
        f"📌 **Already Joined Accounts:** `{already_joined_count}`\n"
        f"✨ **Newly Joined Accounts:** `{newly_joined_count}`\n"
        f"❌ **Failed Accounts:** `{failed_count}`\n\n"
        f"🏆 **Total Successfully Joined Accounts:** `{total_successful_joined}`"
    )

    await update.message.reply_text(
        report_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user_id)
    )

    return ConversationHandler.END

# ----------------- BUTTON 4: LEAVE CHANNEL -----------------
async def leave_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return ConversationHandler.END

    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM accounts")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        await update.message.reply_text(f"⚠️ Filhal bot me koi account added nahi hai.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🚪 **Enter Channel / Group Link to Leave:**\n\n"
        "• Public Link: `https://t.me/yourchannel` ya `@yourchannel`\n"
        "• Private Link: `https://t.me/+abcdef...` ya `https://t.me/joinchat/...`",
        parse_mode="Markdown"
    )
    return WAITING_LEAVE_LINK

async def receive_leave_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link = update.message.text.strip()

    if link.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    if not (link.startswith("https://t.me/") or link.startswith("t.me/") or link.startswith("@")):
        await update.message.reply_text(
            "❌ **Ye koi valid Telegram Link nahi hai!**\n\n"
            "Kripya sahi link bhejiyen (e.g. `https://t.me/...` ya `@channelname`):",
            parse_mode="Markdown"
        )
        return WAITING_LEAVE_LINK

    status_msg = await update.message.reply_text("🔍 Accounts check kiye ja rahe hain, kripya thoda intzar karein...")

    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT first_name, username, string_session FROM accounts")
    accounts = cursor.fetchall()
    conn.close()

    joined_sessions = []
    not_joined_count = 0

    for acc in accounts:
        first_name, username, session_str = acc
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()

            entity = await client.get_entity(link)
            try:
                participant = await client(functions.channels.GetParticipantRequest(channel=entity, participant='me'))
                if participant:
                    joined_sessions.append((first_name, session_str, entity))
                else:
                    not_joined_count += 1
            except Exception:
                not_joined_count += 1

            await client.disconnect()

        except Exception as e:
            not_joined_count += 1
            try:
                await client.disconnect()
            except Exception:
                pass

    total_acc = len(accounts)
    joined_count = len(joined_sessions)

    context.user_data['joined_sessions'] = joined_sessions
    context.user_data['leave_link'] = link

    if joined_count == 0:
        await status_msg.edit_text(
            f"📊 **Account Status Check Complete:**\n\n"
            f"👤 **Total Accounts:** `{total_acc}`\n"
            f"✅ **Account Channel Joined:** `0`\n"
            f"❌ **Account Channel Not Joined:** `{total_acc}`\n\n"
            f"⚠️ Is channel me koi bhi account joined nahi hai."
        )
        return ConversationHandler.END

    await status_msg.edit_text(
        f"📊 **Account Status Summary:**\n\n"
        f"👤 **Total Accounts:** `{total_acc}`\n"
        f"✅ **Account Channel Joined:** `{joined_count}`\n"
        f"❌ **Account Channel Not Joined:** `{not_joined_count}`\n\n"
        f"❓ Aap in **{joined_count}** joined accounts me se kitne accounts ko leave karwana chahte hain? (1 se {joined_count} tak number bhejiyen):",
        parse_mode="Markdown"
    )
    return WAITING_LEAVE_COUNT

async def receive_leave_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    if not text.isdigit():
        await update.message.reply_text("❌ Galat input! Kripya numeric number bhejiyen:")
        return WAITING_LEAVE_COUNT

    count = int(text)
    joined_sessions = context.user_data.get('joined_sessions', [])
    max_count = len(joined_sessions)

    if count <= 0 or count > max_count:
        await update.message.reply_text(f"❌ Kripya 1 se {max_count} ke beech ka valid number bhejiyen:")
        return WAITING_LEAVE_COUNT

    status_msg = await update.message.reply_text(f"🔄 {count} accounts ko channel se leave karwaya ja raha hai...")

    successfully_left = 0
    failed_leave = 0

    target_to_leave = joined_sessions[:count]

    for item in target_to_leave:
        first_name, session_str, entity = item
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()
            await client(functions.channels.LeaveChannelRequest(channel=entity))
            await client.disconnect()
            successfully_left += 1
        except Exception as e:
            logger.error(f"Error leaving channel for {first_name}: {e}")
            failed_leave += 1
            try:
                await client.disconnect()
            except Exception:
                pass

    await status_msg.edit_text(
        f"🎉 **Process Completed!**\n\n"
        f"✅ Successfully Channel se leave kar diya gaya hai!\n\n"
        f"🚪 **Left Accounts:** `{successfully_left}`\n"
        f"❌ **Failed:** `{failed_leave}`",
        parse_mode="Markdown"
    )

    await update.message.reply_text("Aap menu se doosra option chun sakte hain:", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

# ----------------- BUTTON 5: REACTION FEATURE (FIXED) -----------------
async def reaction_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return ConversationHandler.END

    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM accounts")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        await update.message.reply_text("⚠️ Filhal bot me koi account added nahi hai. Pehle account add karein.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🎭 **Send Channel / Group Link:**\n\n"
        "• Public Link: `https://t.me/yourchannel` ya `@yourchannel`\n"
        "• Private Link: `https://t.me/+abcdef...` ya `https://t.me/joinchat/...`",
        parse_mode="Markdown"
    )
    return WAITING_REACT_CHAN_LINK

async def receive_react_chan_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link = update.message.text.strip()

    if link.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    if not (link.startswith("https://t.me/") or link.startswith("t.me/") or link.startswith("@")):
        await update.message.reply_text("❌ Invalid link! Kripya sahi Telegram channel link bhejiyen:")
        return WAITING_REACT_CHAN_LINK

    status_msg = await update.message.reply_text("🔍 Channel & Accounts status check kiya ja raha hai...")

    is_private = "+" in link or "joinchat" in link
    chan_type = "Private 🔒" if is_private else "Public 🌐"

    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT first_name, string_session FROM accounts")
    accounts = cursor.fetchall()
    conn.close()

    total_acc = len(accounts)
    joined_accs = []
    not_joined_accs = []

    clean_link = link.split("/")[-1].replace("@", "") if not is_private else link

    for acc in accounts:
        first_name, session_str = acc
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()
            try:
                entity = await client.get_entity(clean_link)
                participant = await client(functions.channels.GetParticipantRequest(channel=entity, participant='me'))
                if participant:
                    joined_accs.append((first_name, session_str))
                else:
                    not_joined_accs.append((first_name, session_str))
            except Exception:
                not_joined_accs.append((first_name, session_str))
            await client.disconnect()
        except Exception:
            not_joined_accs.append((first_name, session_str))

    context.user_data['is_private'] = is_private
    context.user_data['channel_type'] = chan_type
    context.user_data['chan_link'] = clean_link
    context.user_data['total_accounts'] = total_acc
    context.user_data['joined_accs'] = joined_accs
    context.user_data['not_joined_accs'] = not_joined_accs
    context.user_data['all_accounts'] = accounts

    report_str = (
        f"📊 **Channel & Account Status Report:**\n\n"
        f"📌 **Channel Type:** `{chan_type}`\n"
        f"👤 **Total Accounts:** `{total_acc}`\n"
        f"✅ **Joined Accounts:** `{len(joined_accs)}`\n"
        f"❌ **Not Joined Accounts:** `{len(not_joined_accs)}`\n\n"
        f"📥 **Ab kripya us POST ka link bhejiyen jis par reaction dena chahte hain:**"
    )

    await status_msg.edit_text(report_str, parse_mode="Markdown")
    return WAITING_REACT_POST_LINK

async def receive_react_post_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    post_link = update.message.text.strip()

    if post_link.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    msg_id = parse_post_link(post_link)
    if not msg_id:
        await update.message.reply_text("❌ Galat Post link! Kripya sahi post URL bhejiyen (e.g. `https://t.me/channel/123`):")
        return WAITING_REACT_POST_LINK

    context.user_data['post_link'] = post_link
    context.user_data['msg_id'] = msg_id

    is_private = context.user_data['is_private']
    joined_accs = context.user_data['joined_accs']
    all_accounts = context.user_data['all_accounts']

    if is_private:
        max_available = len(joined_accs)
        if max_available == 0:
            await update.message.reply_text("⚠️ Ye channel Private hai aur aapka koi bhi account isme Joined nahi hai.")
            return ConversationHandler.END
        
        await update.message.reply_text(
            f"🔒 **Private Channel Detected!**\n"
            f"Aapke **{max_available}** accounts joined hain.\n\n"
            f"Aap kitne accounts se reaction dena chahte hain? (1 se {max_available} tak number bhejiyen):",
            parse_mode="Markdown"
        )
    else:
        max_available = len(all_accounts)
        await update.message.reply_text(
            f"🌐 **Public Channel Detected!**\n"
            f"Total **{max_available}** accounts available hain.\n\n"
            f"Aap kitne accounts se reaction dena chahte hain? (1 se {max_available} tak number bhejiyen):",
            parse_mode="Markdown"
        )

    context.user_data['max_available'] = max_available
    return WAITING_REACT_COUNT

async def receive_react_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    if not text.isdigit():
        await update.message.reply_text("❌ Invalid input! Kripya number bhejiyen:")
        return WAITING_REACT_COUNT

    count = int(text)
    max_available = context.user_data.get('max_available', 1)

    if count <= 0 or count > max_available:
        await update.message.reply_text(f"❌ Kripya 1 se {max_available} ke beech ka number bhejiyen:")
        return WAITING_REACT_COUNT

    context.user_data['selected_count'] = count

    await update.message.reply_text(
        "⏱ **Delay Setting:**\n\n"
        "Har reaction ke beech kitne **Seconds** ka delay/interval hona chahiye? (e.g. `2` ya `3`):",
        parse_mode="Markdown"
    )
    return WAITING_REACT_DELAY

async def receive_react_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    if not text.isdigit():
        await update.message.reply_text("❌ Invalid input! Kripya numeric seconds bhejiyen:")
        return WAITING_REACT_DELAY

    delay = int(text)
    context.user_data['react_delay'] = delay

    inline_kbd = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 Single Emoji", callback_data="react_mode_single"),
            InlineKeyboardButton("🎭 Multiple Emoji", callback_data="react_mode_multi")
        ]
    ])

    await update.message.reply_text(
        "⚙️ **Select Reaction Emoji Mode:**\n\n"
        "• **Single Emoji:** Sabhi accounts same 1 emoji bhejenge.\n"
        "• **Multiple Emoji:** Har emoji ke beech space dekar bhejiyen, barabar distribute ho jayenge.",
        reply_markup=inline_kbd,
        parse_mode="Markdown"
    )
    return WAITING_REACT_MODE_SELECT

async def react_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "react_mode_single":
        await query.edit_message_text("👍 **Send 1 Emoji:**\n\nKripya wo 1 Emoji bhejiyen jo aap reaction me dena chahte hain:")
        return WAITING_REACT_SINGLE_EMOJI
    elif data == "react_mode_multi":
        await query.edit_message_text("🎭 **Send Multiple Emojis:**\n\nEmojis ke beech space laga kar bhejiyen (e.g. `❤️ 🔥 👍 😂`):")
        return WAITING_REACT_MULTI_EMOJI

async def receive_react_single_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    emoji_text = update.message.text.strip()

    if emoji_text.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    context.user_data['emoji_list'] = [emoji_text]
    await execute_reactions(update, context)
    return ConversationHandler.END

async def receive_react_multi_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    emojis = text.split()
    if not emojis:
        await update.message.reply_text("❌ Kripya kam se kam 1 emoji bhejiyen:")
        return WAITING_REACT_MULTI_EMOJI

    context.user_data['emoji_list'] = emojis
    await execute_reactions(update, context)
    return ConversationHandler.END

async def execute_reactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_private = context.user_data['is_private']
    joined_accs = context.user_data['joined_accs']
    all_accounts = context.user_data['all_accounts']
    selected_count = context.user_data['selected_count']
    delay = context.user_data['react_delay']
    emoji_list = context.user_data['emoji_list']
    chan_link = context.user_data['chan_link']
    msg_id = context.user_data['msg_id']

    target_accs = joined_accs[:selected_count] if is_private else all_accounts[:selected_count]

    await update.message.reply_text(
        f"✅ **Order Successfully Submitted!**\n\n"
        f"👥 **Accounts:** `{len(target_accs)}`\n"
        f"⏱ **Delay:** `{delay}` Seconds\n"
        f"🎭 **Emojis:** {' '.join(emoji_list)}\n\n"
        f"🔄 Reaction process chalu ho gaya hai...",
        parse_mode="Markdown"
    )

    success_count = 0
    fail_count = 0

    for idx, acc in enumerate(target_accs):
        await asyncio.sleep(delay)
        first_name, session_str = acc
        assigned_emoji = emoji_list[idx % len(emoji_list)]

        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()

            if is_private:
                entity = await client.get_entity(chan_link)
            else:
                target_entity = chan_link.split("/")[-1].replace("@", "")
                entity = await client.get_entity(target_entity)

            # Send Reaction
            await client(functions.messages.SendReactionRequest(
                peer=entity,
                msg_id=msg_id,
                reaction=[functions.types.ReactionEmoji(emoticon=assigned_emoji)]
            ))

            await client.disconnect()
            success_count += 1
            logger.info(f"Reaction {assigned_emoji} sent by {first_name}")

        except Exception as e:
            logger.error(f"Failed reaction for {first_name}: {e}")
            
            # Auto Retry Strategy for Public Channels
            try:
                if not is_private:
                    target_entity = chan_link.split("/")[-1].replace("@", "")
                    await client(functions.channels.JoinChannelRequest(channel=target_entity))
                    entity = await client.get_entity(target_entity)
                    await client(functions.messages.SendReactionRequest(
                        peer=entity,
                        msg_id=msg_id,
                        reaction=[functions.types.ReactionEmoji(emoticon=assigned_emoji)]
                    ))
                    success_count += 1
                else:
                    fail_count += 1
            except Exception:
                fail_count += 1

            try:
                await client.disconnect()
            except Exception:
                pass

    report = (
        f"🎉 **Reaction Process Completed!**\n\n"
        f"✅ **Successful Reactions:** `{success_count}`\n"
        f"❌ **Failed:** `{fail_count}`\n\n"
        f"📌 Aap apne post par reactions check kar sakte hain!"
    )

    await update.message.reply_text(
        report,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user_id)
    )

# ----------------- BUTTON 6: ALL ADMIN LIST -----------------
async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ Access Denied.")
        return ConversationHandler.END

    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    rows = cursor.fetchall()
    conn.close()

    text = f"👑 **Main Owner ID:** `{OWNER_ID}`\n\n"
    if not rows:
        text += "👥 **Total Admins:** `0`\nℹ️ _Koi extra admin added nahi hai._"
    else:
        text += f"👥 **Total Admins:** `{len(rows)}`\n\n📜 **Admin List:**\n"
        for idx, row in enumerate(rows, start=1):
            text += f"{idx}. ID: `{row[0]}`\n"

    await update.message.reply_text(text, parse_mode="Markdown")
    return ConversationHandler.END

# ----------------- BUTTON 7: ADD ADMIN -----------------
async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Sirf Main Owner hi Admin add kar sakta hai.")
        return ConversationHandler.END

    await update.message.reply_text(
        "👤 **Add New Admin:**\n\nJis user ko Admin banana hai, uska **Numeric Chat ID** bhejiyen:",
        parse_mode="Markdown"
    )
    return WAITING_ADMIN_ID

async def receive_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text.lower() == "/cancel":
        await update.message.reply_text("❌ Process cancel kar diya gaya.", reply_markup=get_main_keyboard(user_id))
        return ConversationHandler.END

    if not text.isdigit():
        await update.message.reply_text("❌ Galat Chat ID! Kripya sirf numeric Chat ID bhejiyen:")
        return WAITING_ADMIN_ID

    new_admin_id = int(text)
    if new_admin_id == OWNER_ID:
        await update.message.reply_text("⚠️ Aap pehle se Main Owner hain!")
        return ConversationHandler.END

    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO admins (user_id) VALUES (?)", (new_admin_id,))
        conn.commit()
        await update.message.reply_text(
            f"✅ **Success!** ID `{new_admin_id}` ko Admin bana diya gaya hai.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id)
        )
    except sqlite3.IntegrityError:
        await update.message.reply_text("⚠️ Ye User ID pehle se Admin hai!")
    finally:
        conn.close()

    return ConversationHandler.END

# ----------------- BUTTON 8: REMOVE ADMIN -----------------
async def remove_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔ Sirf Main Owner hi Admin remove kar sakta hai.")
        return ConversationHandler.END

    conn = sqlite3.connect('accounts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("❌ Remove karne ke liye koi Admin added nahi hai.")
        return ConversationHandler.END

    keyboard = []
    for idx, row in enumerate(rows, start=1):
        adm_id = row[0]
        keyboard.append([InlineKeyboardButton(f"📛 Admin ID: {adm_id}", callback_data=f"ask_rem_adm_{adm_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📛 Jis Admin ko hatana hai us par click karein:", reply_markup=reply_markup)
    return ConversationHandler.END

# Inline Buttons Callbacks
async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("ask_rem_acc_"):
        db_id = data.split("_")[3]
        conn = sqlite3.connect('accounts.db')
        cursor = conn.cursor()
        cursor.execute("SELECT first_name, user_id FROM accounts WHERE id = ?", (db_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            await query.edit_message_text("❌ Ye account pehle hi remove ho chuka hai.")
            return

        first_name, acc_id = row
        confirm_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"confirm_rem_acc_{db_id}"),
                InlineKeyboardButton("❌ No", callback_data="cancel_rem")
            ]
        ])
        await query.edit_message_text(
            f"❓ Kya aap `{first_name}` (ID: `{acc_id}`) ko remove karna chahte hain?",
            reply_markup=confirm_keyboard,
            parse_mode="Markdown"
        )

    elif data.startswith("confirm_rem_acc_"):
        db_id = data.split("_")[3]
        conn = sqlite3.connect('accounts.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (db_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ Account successfully remove ho gaya hai!")

    elif data.startswith("ask_rem_adm_"):
        adm_id = data.split("_")[3]
        confirm_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"confirm_rem_adm_{adm_id}"),
                InlineKeyboardButton("❌ No", callback_data="cancel_rem")
            ]
        ])
        await query.edit_message_text(
            f"❓ Kya aap Admin ID `{adm_id}` ko hatana chahte hain?",
            reply_markup=confirm_keyboard,
            parse_mode="Markdown"
        )

    elif data.startswith("confirm_rem_adm_"):
        adm_id = data.split("_")[3]
        conn = sqlite3.connect('accounts.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (adm_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ Admin successfully remove ho gaya hai!")

    elif data == "cancel_rem":
        await query.edit_message_text("❌ Action cancelled.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("Process cancelled.", reply_markup=get_main_keyboard(user_id))
    return ConversationHandler.END

# Main Function
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    admin_list_handler = MessageHandler(filters.Regex(f"^{re.escape(BTN_LIST_ADM)}$"), admin_list)
    remove_acc_handler = MessageHandler(filters.Regex(f"^{re.escape(BTN_REM_ACC)}$"), remove_account_start)
    remove_adm_handler = MessageHandler(filters.Regex(f"^{re.escape(BTN_REM_ADM)}$"), remove_admin_start)

    button_fallbacks = [
        CommandHandler("cancel", cancel),
        MessageHandler(filters.Regex(f"^{re.escape(BTN_JOIN)}$"), join_channel_start),
        MessageHandler(filters.Regex(f"^{re.escape(BTN_LEAVE)}$"), leave_channel_start),
        MessageHandler(filters.Regex(f"^{re.escape(BTN_REACTION)}$"), reaction_start),
        MessageHandler(filters.Regex(f"^{re.escape(BTN_ADD_ACC)}$"), add_account_start),
        admin_list_handler,
        remove_acc_handler,
        remove_adm_handler,
        MessageHandler(filters.Regex(f"^{re.escape(BTN_ADD_ADM)}$"), add_admin_start)
    ]

    add_acc_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BTN_ADD_ACC)}$"), add_account_start)],
        states={
            WAITING_STRING_SESSION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_string_session)
            ]
        },
        fallbacks=button_fallbacks
    )

    add_adm_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BTN_ADD_ADM)}$"), add_admin_start)],
        states={
            WAITING_ADMIN_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_admin_id)
            ]
        },
        fallbacks=button_fallbacks
    )

    join_chan_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BTN_JOIN)}$"), join_channel_start)],
        states={
            WAITING_JOIN_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_join_link)],
            WAITING_JOIN_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_join_count)],
            WAITING_JOIN_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_join_delay)]
        },
        fallbacks=button_fallbacks
    )

    leave_chan_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BTN_LEAVE)}$"), leave_channel_start)],
        states={
            WAITING_LEAVE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_leave_link)],
            WAITING_LEAVE_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_leave_count)]
        },
        fallbacks=button_fallbacks
    )

    reaction_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BTN_REACTION)}$"), reaction_start)],
        states={
            WAITING_REACT_CHAN_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_react_chan_link)],
            WAITING_REACT_POST_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_react_post_link)],
            WAITING_REACT_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_react_count)],
            WAITING_REACT_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_react_delay)],
            WAITING_REACT_MODE_SELECT: [CallbackQueryHandler(react_mode_callback)],
            WAITING_REACT_SINGLE_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_react_single_emoji)],
            WAITING_REACT_MULTI_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, receive_react_multi_emoji)],
        },
        fallbacks=button_fallbacks
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(add_acc_handler)
    application.add_handler(add_adm_handler)
    application.add_handler(join_chan_handler)
    application.add_handler(leave_chan_handler)
    application.add_handler(reaction_handler)
    application.add_handler(admin_list_handler)
    application.add_handler(remove_acc_handler)
    application.add_handler(remove_adm_handler)
    application.add_handler(CallbackQueryHandler(button_click_handler))

    print("Bot startup completed. Polling started...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
