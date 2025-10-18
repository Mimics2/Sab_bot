import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
DB_PATH = "/tmp/bot.db" if os.path.exists("/tmp") else "bot.db"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PremiumDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Пользователи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Каналы для проверки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscription_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_username TEXT,
                channel_url TEXT,
                channel_name TEXT,
                channel_type TEXT DEFAULT 'public',
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Подтвержденные подписки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS confirmed_subscriptions (
                user_id INTEGER,
                channel_id INTEGER,
                confirmed BOOLEAN DEFAULT FALSE,
                confirmed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, channel_id)
            )
        ''')
        
        # Финальные каналы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referral_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_url TEXT NOT NULL,
                channel_name TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Premium Database инициализирована")

    def add_user(self, user_id, username, full_name):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)', 
                         (user_id, username, full_name))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"❌ Ошибка добавления пользователя: {e}")

    def add_subscription_channel(self, channel_username, channel_url, channel_name, channel_type='public'):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO subscription_channels (channel_username, channel_url, channel_name, channel_type) VALUES (?, ?, ?, ?)',
                         (channel_username, channel_url, channel_name, channel_type))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления канала: {e}")
            return False

    def get_subscription_channels(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM subscription_channels ORDER BY id')
            channels = cursor.fetchall()
            conn.close()
            return channels
        except Exception as e:
            logger.error(f"❌ Ошибка получения каналов: {e}")
            return []

    def confirm_subscription(self, user_id, channel_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO confirmed_subscriptions (user_id, channel_id, confirmed) VALUES (?, ?, TRUE)',
                         (user_id, channel_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подтверждения: {e}")
            return False

    def is_subscription_confirmed(self, user_id, channel_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT confirmed FROM confirmed_subscriptions WHERE user_id = ? AND channel_id = ?',
                         (user_id, channel_id))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else False
        except Exception as e:
            logger.error(f"❌ Ошибка проверки: {e}")
            return False

    def remove_subscription_confirmation(self, user_id, channel_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM confirmed_subscriptions WHERE user_id = ? AND channel_id = ?',
                         (user_id, channel_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления подтверждения: {e}")
            return False

    def add_referral_channel(self, channel_url, channel_name):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO referral_channels (channel_url, channel_name) VALUES (?, ?)',
                         (channel_url, channel_name))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления финального канала: {e}")
            return False

    def get_referral_channels(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM referral_channels ORDER BY id')
            channels = cursor.fetchall()
            conn.close()
            return channels
        except Exception as e:
            logger.error(f"❌ Ошибка получения финальных каналов: {e}")
            return []

    def remove_subscription_channel(self, channel_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM subscription_channels WHERE id = ?', (channel_id,))
            cursor.execute('DELETE FROM confirmed_subscriptions WHERE channel_id = ?', (channel_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления канала: {e}")
            return False

    def remove_referral_channel(self, channel_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM referral_channels WHERE id = ?', (channel_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления финального канала: {e}")
            return False

    def get_all_users(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users')
            users = cursor.fetchall()
            conn.close()
            return users
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователей: {e}")
            return []

# Инициализация базы данных
try:
    db = PremiumDatabase(DB_PATH)
    logger.info("✅ Premium Database загружена")
except Exception as e:
    logger.error(f"❌ Критическая ошибка БД: {e}")
    db = None

async def check_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Улучшенная проверка подписок с исправлением багов"""
    user = update.effective_user
    bot = context.bot
    channels = db.get_subscription_channels()
    
    result = {
        "all_subscribed": True,
        "missing_channels": []
    }
    
    if not channels:
        return result
    
    for channel in channels:
        channel_id, channel_username, channel_url, channel_name, channel_type, _ = channel
        
        if channel_type == 'public':
            # Проверка публичных каналов
            try:
                if channel_username:
                    clean_username = channel_username.lstrip('@')
                    chat_member = await bot.get_chat_member(f"@{clean_username}", user.id)
                    subscribed = chat_member.status in ['member', 'administrator', 'creator']
                    
                    if not subscribed:
                        result["all_subscribed"] = False
                        result["missing_channels"].append({
                            "id": channel_id,
                            "name": channel_name,
                            "type": "public",
                            "url": f"https://t.me/{clean_username}"
                        })
                else:
                    result["all_subscribed"] = False
                    result["missing_channels"].append({
                        "id": channel_id,
                        "name": channel_name,
                        "type": "public",
                        "url": channel_url
                    })
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки {channel_username}: {e}")
                result["all_subscribed"] = False
                result["missing_channels"].append({
                    "id": channel_id,
                    "name": channel_name,
                    "type": "public",
                    "url": f"https://t.me/{clean_username}" if channel_username else channel_url
                })
        
        elif channel_type == 'private':
            # ИСПРАВЛЕННЫЙ КОД: проверяем фактическую подписку, а не только подтверждение
            if channel_username:
                try:
                    clean_username = channel_username.lstrip('@')
                    chat_member = await bot.get_chat_member(f"@{clean_username}", user.id)
                    actually_subscribed = chat_member.status in ['member', 'administrator', 'creator']
                    
                    if actually_subscribed:
                        # Автоматически подтверждаем если подписан
                        db.confirm_subscription(user.id, channel_id)
                    else:
                        # Сбрасываем подтверждение если не подписан
                        db.remove_subscription_confirmation(user.id, channel_id)
                        result["all_subscribed"] = False
                        result["missing_channels"].append({
                            "id": channel_id,
                            "name": channel_name,
                            "type": "private",
                            "url": channel_url
                        })
                        
                except Exception as e:
                    # Если не можем проверить, используем подтверждение из БД
                    confirmed = db.is_subscription_confirmed(user.id, channel_id)
                    if not confirmed:
                        result["all_subscribed"] = False
                        result["missing_channels"].append({
                            "id": channel_id,
                            "name": channel_name,
                            "type": "private",
                            "url": channel_url
                        })
            else:
                # Если username не указан, используем только подтверждение
                confirmed = db.is_subscription_confirmed(user.id, channel_id)
                if not confirmed:
                    result["all_subscribed"] = False
                    result["missing_channels"].append({
                        "id": channel_id,
                        "name": channel_name,
                        "type": "private",
                        "url": channel_url
                    })
    
    return result

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db is None:
        await update.message.reply_text("🚫 Сервис временно недоступен")
        return
        
    user = update.effective_user
    db.add_user(user.id, user.username, user.full_name)

    subscription_status = await check_subscriptions(update, context)
    
    if subscription_status["all_subscribed"]:
        await show_success_message(update, context)
    else:
        await show_subscription_request(update, context, subscription_status["missing_channels"])

async def show_success_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    referral_channels = db.get_referral_channels()
    
    if not referral_channels:
        message = "✨ Отлично! Вы подписаны на все каналы"
        if update.callback_query:
            await update.callback_query.edit_message_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    channel = referral_channels[0]
    channel_id, channel_url, channel_name, _ = channel
    
    text = f"""
🎉 **Premium Access Activated!**

💎 **Your exclusive link:**
{channel_url}

⚡ Click below to join
    """
    
    keyboard = [
        [InlineKeyboardButton(f"🚀 Join {channel_name}", url=channel_url)],
        [InlineKeyboardButton("🔄 Check Subscription", callback_data="check_subs")]
    ]
    
    if update.effective_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_subscription_request(update: Update, context: ContextTypes.DEFAULT_TYPE, missing_channels=None):
    keyboard = []
    
    for channel_info in missing_channels:
        if channel_info["type"] == "public":
            keyboard.append([
                InlineKeyboardButton(
                    f"📺 Subscribe to {channel_info['name']}",
                    url=channel_info["url"]
                )
            ])
        elif channel_info["type"] == "private":
            keyboard.append([
                InlineKeyboardButton(
                    f"🔗 Join {channel_info['name']}",
                    url=channel_info["url"]
                ),
                InlineKeyboardButton(
                    f"✅ Confirm {channel_info['name']}",
                    callback_data=f"confirm_{channel_info['id']}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔄 Check All Subscriptions", callback_data="check_subs")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if missing_channels:
        public_channels = [ch["name"] for ch in missing_channels if ch["type"] == "public"]
        private_channels = [ch["name"] for ch in missing_channels if ch["type"] == "private"]
        
        text = "📋 **Premium Access Requirements:**\n\n"
        
        if public_channels:
            text += f"• Subscribe to: **{', '.join(public_channels)}**\n"
        
        if private_channels:
            text += f"• Join private channels: **{', '.join(private_channels)}**\n"
            text += "  *(click 'Confirm' after joining)*\n"
        
        text += "\n👇 Use buttons below"
    else:
        text = "📋 Subscription required for access"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    
    if query.data == "check_subs":
        db.add_user(user.id, user.username, user.full_name)
        subscription_status = await check_subscriptions(update, context)
        
        if subscription_status["all_subscribed"]:
            await show_success_message(update, context)
        else:
            await show_subscription_request(update, context, subscription_status["missing_channels"])
    
    elif query.data.startswith("confirm_"):
        channel_id = int(query.data.replace("confirm_", ""))
        
        if db.confirm_subscription(user.id, channel_id):
            await query.answer("✅ Subscription confirmed!", show_alert=True)
            
            subscription_status = await check_subscriptions(update, context)
            
            if subscription_status["all_subscribed"]:
                await show_success_message(update, context)
            else:
                await show_subscription_request(update, context, subscription_status["missing_channels"])
        else:
            await query.answer("❌ Confirmation error", show_alert=True)
    
    elif query.data == "admin_panel":
        if user.id == ADMIN_ID:
            await show_admin_panel(update, context)
        else:
            await query.answer("🚫 Access denied", show_alert=True)

    elif query.data == "manage_channels":
        if user.id == ADMIN_ID:
            await show_manage_channels(update, context)
        else:
            await query.answer("🚫 Access denied", show_alert=True)

    elif query.data == "add_public_channel":
        if user.id == ADMIN_ID:
            context.user_data['awaiting_channel'] = True
            context.user_data['channel_type'] = 'public'
            await query.edit_message_text(
                "➕ **Add Public Channel**\n\nFormat:\n`@username Channel Name`\n\nExample:\n`@my_channel My Channel`",
                parse_mode='Markdown'
            )
        else:
            await query.answer("🚫 Access denied", show_alert=True)

    elif query.data == "add_private_channel":
        if user.id == ADMIN_ID:
            context.user_data['awaiting_channel'] = True
            context.user_data['channel_type'] = 'private'
            await query.edit_message_text(
                "➕ **Add Private Channel**\n\nFormat:\n`link Channel Name`\n\nExample:\n`https://t.me/my_channel Private Channel`",
                parse_mode='Markdown'
            )
        else:
            await query.answer("🚫 Access denied", show_alert=True)

    elif query.data == "add_referral_channel":
        if user.id == ADMIN_ID:
            context.user_data['awaiting_channel'] = True
            context.user_data['channel_type'] = 'referral'
            await query.edit_message_text(
                "💎 **Add Final Channel**\n\nFormat:\n`link Channel Name`\n\nExample:\n`https://t.me/final_channel Premium Content`",
                parse_mode='Markdown'
            )
        else:
            await query.answer("🚫 Access denied", show_alert=True)

    elif query.data.startswith("delete_sub_"):
        if user.id == ADMIN_ID:
            channel_id = int(query.data.replace("delete_sub_", ""))
            if db.remove_subscription_channel(channel_id):
                await query.edit_message_text("✅ Channel deleted!")
            else:
                await query.edit_message_text("❌ Delete error!")
            await show_manage_channels(update, context)
        else:
            await query.answer("🚫 Access denied", show_alert=True)

    elif query.data.startswith("delete_ref_"):
        if user.id == ADMIN_ID:
            channel_id = int(query.data.replace("delete_ref_", ""))
            if db.remove_referral_channel(channel_id):
                await query.edit_message_text("✅ Channel deleted!")
            else:
                await query.edit_message_text("❌ Delete error!")
            await show_manage_channels(update, context)
        else:
            await query.answer("🚫 Access denied", show_alert=True)

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db is None:
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Database unavailable")
        else:
            await update.message.reply_text("❌ Database unavailable")
        return
        
    total_users = len(db.get_all_users())
    sub_channels = db.get_subscription_channels()
    ref_channels = db.get_referral_channels()
    
    text = f"""
⚙️ **Premium Admin Panel**

📊 **Statistics:**
• 👥 Users: {total_users}
• 📺 Check Channels: {len(sub_channels)}
• 💎 Final Channels: {len(ref_channels)}

**Available actions:**
    """
    
    keyboard = [
        [InlineKeyboardButton("📺 Manage Channels", callback_data="manage_channels")],
        [InlineKeyboardButton("◀️ Back", callback_data="check_subs")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_manage_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sub_channels = db.get_subscription_channels()
    ref_channels = db.get_referral_channels()
    
    text = "🔧 **Channel Management:**\n\n"
    
    text += "📺 **Subscription Channels:**\n"
    if sub_channels:
        for channel in sub_channels:
            text += f"• {channel[3]} ({channel[4]})\n"
    else:
        text += "No channels\n"
    
    text += "\n💎 **Final Channels:**\n"
    if ref_channels:
        for channel in ref_channels:
            text += f"• {channel[2]}\n"
    else:
        text += "No channels\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Public Channel", callback_data="add_public_channel")],
        [InlineKeyboardButton("➕ Private Channel", callback_data="add_private_channel")],
        [InlineKeyboardButton("➕ Final Channel", callback_data="add_referral_channel")]
    ]
    
    for channel in sub_channels:
        keyboard.append([InlineKeyboardButton(f"🗑️ Delete {channel[3]}", callback_data=f"delete_sub_{channel[0]}")])
    
    for channel in ref_channels:
        keyboard.append([InlineKeyboardButton(f"🗑️ Delete {channel[2]}", callback_data=f"delete_ref_{channel[0]}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
        
    if context.user_data.get('awaiting_channel'):
        channel_type = context.user_data.get('channel_type')
        
        try:
            text = update.message.text.strip()
            
            if channel_type == 'public':
                parts = text.split(' ', 1)
                if len(parts) == 2 and parts[0].startswith('@'):
                    channel_username = parts[0]
                    channel_name = parts[1]
                    
                    if db.add_subscription_channel(channel_username, f"https://t.me/{channel_username.lstrip('@')}", channel_name, 'public'):
                        await update.message.reply_text(f"✅ Channel {channel_name} added!")
                    else:
                        await update.message.reply_text("❌ Add error!")
                else:
                    await update.message.reply_text("❌ Format: `@username Channel Name`", parse_mode='Markdown')
                
                context.user_data['awaiting_channel'] = False
                await show_manage_channels(update, context)
                
            elif channel_type == 'private':
                parts = text.split(' ', 1)
                if len(parts) == 2:
                    channel_url = parts[0]
                    channel_name = parts[1]
                    
                    if db.add_subscription_channel(None, channel_url, channel_name, 'private'):
                        await update.message.reply_text(f"✅ Channel {channel_name} added!")
                    else:
                        await update.message.reply_text("❌ Add error!")
                else:
                    await update.message.reply_text("❌ Format: `link Channel Name`")
                
                context.user_data['awaiting_channel'] = False
                await show_manage_channels(update, context)
                
            elif channel_type == 'referral':
                parts = text.split(' ', 1)
                if len(parts) == 2:
                    channel_url = parts[0]
                    channel_name = parts[1]
                    
                    if db.add_referral_channel(channel_url, channel_name):
                        await update.message.reply_text(f"✅ Final channel {channel_name} added!")
                    else:
                        await update.message.reply_text("❌ Add error!")
                else:
                    await update.message.reply_text("❌ Format: `link Channel Name`")
                
                context.user_data['awaiting_channel'] = False
                await show_manage_channels(update, context)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
            context.user_data['awaiting_channel'] = False

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await show_admin_panel(update, context)
    else:
        await update.message.reply_text("🚫 Access denied")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subscription_status = await check_subscriptions(update, context)
    
    if subscription_status["all_subscribed"]:
        await show_success_message(update, context)
    else:
        await update.message.reply_text("❌ Not subscribed to all channels!")
        await show_subscription_request(update, context, subscription_status["missing_channels"])

async def set_commands(application: Application):
    commands = [
        BotCommand("start", "Start bot"),
        BotCommand("check", "Check subscription"), 
        BotCommand("admin", "Admin panel")
    ]
    await application.bot.set_my_commands(commands)

def main():
    if db is None:
        logger.error("❌ Database init failed. Bot stopped.")
        return
        
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Set commands
    application.post_init = set_commands
    
    # Start bot
    logger.info("🚀 Premium Bot starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
