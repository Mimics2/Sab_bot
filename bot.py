import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# === НАСТРОЙКИ ДЛЯ RAILWAY ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")

# Проверка обязательных переменных
if not BOT_TOKEN:
    logging.error("❌ BOT_TOKEN не найден! Добавьте в Railway Variables")
    exit(1)

try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else 0
    if ADMIN_ID == 0:
        logging.error("❌ ADMIN_ID не настроен! Добавьте в Railway Variables")
        exit(1)
except ValueError:
    logging.error("❌ ADMIN_ID должен быть числом!")
    exit(1)

# Путь к БД для Railway
DB_PATH = "/tmp/bot.db"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

logger.info(f"✅ Бот инициализирован. ADMIN_ID: {ADMIN_ID}")

class Database:
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
        logger.info("✅ База данных создана")

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
    db = Database(DB_PATH)
    logger.info("✅ База данных загружена")
except Exception as e:
    logger.error(f"❌ Критическая ошибка БД: {e}")
    db = None

async def check_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Улучшенная проверка подписок"""
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
            if channel_username:
                try:
                    clean_username = channel_username.lstrip('@')
                    chat_member = await bot.get_chat_member(f"@{clean_username}", user.id)
                    actually_subscribed = chat_member.status in ['member', 'administrator', 'creator']
                    
                    if actually_subscribed:
                        db.confirm_subscription(user.id, channel_id)
                    else:
                        db.remove_subscription_confirmation(user.id, channel_id)
                        result["all_subscribed"] = False
                        result["missing_channels"].append({
                            "id": channel_id,
                            "name": channel_name,
                            "type": "private",
                            "url": channel_url
                        })
                        
                except Exception as e:
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
🎉 **Доступ открыт!**

💎 **Ваша ссылка:**
{channel_url}

⚡ Нажмите на кнопку ниже, чтобы перейти
    """
    
    keyboard = [
        [InlineKeyboardButton(f"🚀 Перейти в {channel_name}", url=channel_url)],
        [InlineKeyboardButton("🔄 Проверить подписку", callback_data="check_subs")]
    ]
    
    if update.effective_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Панель управления", callback_data="admin_panel")])
    
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
                    f"📺 Подписаться на {channel_info['name']}",
                    url=channel_info["url"]
                )
            ])
        elif channel_info["type"] == "private":
            keyboard.append([
                InlineKeyboardButton(
                    f"🔗 Перейти в {channel_info['name']}",
                    url=channel_info["url"]
                ),
                InlineKeyboardButton(
                    f"✅ Подтвердить {channel_info['name']}",
                    callback_data=f"confirm_{channel_info['id']}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔄 Проверить все подписки", callback_data="check_subs")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if missing_channels:
        public_channels = [ch["name"] for ch in missing_channels if ch["type"] == "public"]
        private_channels = [ch["name"] for ch in missing_channels if ch["type"] == "private"]
        
        text = "📋 **Для получения доступа необходимо:**\n\n"
        
        if public_channels:
            text += f"• Подписаться на каналы: **{', '.join(public_channels)}**\n"
        
        if private_channels:
            text += f"• Присоединиться к каналам: **{', '.join(private_channels)}**\n"
            text += "  *(после вступления нажмите кнопку 'Подтвердить')*\n"
        
        text += "\n👇 Нажмите на кнопки ниже"
    else:
        text = "📋 Для получения доступа необходимо подписаться на каналы:"
    
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
            await query.answer("✅ Подписка подтверждена!", show_alert=True)
            
            subscription_status = await check_subscriptions(update, context)
            
            if subscription_status["all_subscribed"]:
                await show_success_message(update, context)
            else:
                await show_subscription_request(update, context, subscription_status["missing_channels"])
        else:
            await query.answer("❌ Ошибка подтверждения", show_alert=True)
    
    elif query.data == "admin_panel":
        if user.id == ADMIN_ID:
            await show_admin_panel(update, context)
        else:
            await query.answer("🚫 У вас нет доступа", show_alert=True)

    elif query.data == "manage_channels":
        if user.id == ADMIN_ID:
            await show_manage_channels(update, context)
        else:
            await query.answer("🚫 У вас нет доступа", show_alert=True)

    elif query.data == "add_public_channel":
        if user.id == ADMIN_ID:
            context.user_data['awaiting_channel'] = True
            context.user_data['channel_type'] = 'public'
            await query.edit_message_text(
                "➕ **Добавить публичный канал**\n\nВведите в формате:\n`@username Название`\n\n**Пример:**\n`@my_channel Мой канал`",
                parse_mode='Markdown'
            )
        else:
            await query.answer("🚫 У вас нет доступа", show_alert=True)

    elif query.data == "add_private_channel":
        if user.id == ADMIN_ID:
            context.user_data['awaiting_channel'] = True
            context.user_data['channel_type'] = 'private'
            await query.edit_message_text(
                "➕ **Добавить канал по ссылке**\n\nВведите в формате:\n`ссылка Название`\n\n**Пример:**\n`https://t.me/my_channel Мой канал`",
                parse_mode='Markdown'
            )
        else:
            await query.answer("🚫 У вас нет доступа", show_alert=True)

    elif query.data == "add_referral_channel":
        if user.id == ADMIN_ID:
            context.user_data['awaiting_channel'] = True
            context.user_data['channel_type'] = 'referral'
            await query.edit_message_text(
                "💎 **Добавить финальный канал**\n\nВведите в формате:\n`ссылка Название`\n\n**Пример:**\n`https://t.me/final_channel Основной канал`",
                parse_mode='Markdown'
            )
        else:
            await query.answer("🚫 У вас нет доступа", show_alert=True)

    elif query.data.startswith("delete_sub_"):
        if user.id == ADMIN_ID:
            channel_id = int(query.data.replace("delete_sub_", ""))
            if db.remove_subscription_channel(channel_id):
                await query.edit_message_text("✅ Канал удален!")
            else:
                await query.edit_message_text("❌ Ошибка при удалении!")
            await show_manage_channels(update, context)
        else:
            await query.answer("🚫 У вас нет доступа", show_alert=True)

    elif query.data.startswith("delete_ref_"):
        if user.id == ADMIN_ID:
            channel_id = int(query.data.replace("delete_ref_", ""))
            if db.remove_referral_channel(channel_id):
                await query.edit_message_text("✅ Канал удален!")
            else:
                await query.edit_message_text("❌ Ошибка при удалении!")
            await show_manage_channels(update, context)
        else:
            await query.answer("🚫 У вас нет доступа", show_alert=True)

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db is None:
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ База данных недоступна")
        else:
            await update.message.reply_text("❌ База данных недоступна")
        return
        
    total_users = len(db.get_all_users())
    sub_channels = db.get_subscription_channels()
    ref_channels = db.get_referral_channels()
    
    text = f"""
⚙️ **Панель управления**

📊 **Статистика:**
• 👥 Пользователей: {total_users}
• 📺 Каналов для проверки: {len(sub_channels)}
• 💎 Финальных каналов: {len(ref_channels)}

**Доступные действия:**
    """
    
    keyboard = [
        [InlineKeyboardButton("📺 Управление каналами", callback_data="manage_channels")],
        [InlineKeyboardButton("◀️ Назад", callback_data="check_subs")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_manage_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sub_channels = db.get_subscription_channels()
    ref_channels = db.get_referral_channels()
    
    text = "🔧 **Управление каналами:**\n\n"
    
    text += "📺 **Каналы для проверки:**\n"
    if sub_channels:
        for channel in sub_channels:
            text += f"• {channel[3]} ({channel[4]})\n"
    else:
        text += "Нет каналов\n"
    
    text += "\n💎 **Финальные каналы:**\n"
    if ref_channels:
        for channel in ref_channels:
            text += f"• {channel[2]}\n"
    else:
        text += "Нет каналов\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Публичный канал", callback_data="add_public_channel")],
        [InlineKeyboardButton("➕ Канал по ссылке", callback_data="add_private_channel")],
        [InlineKeyboardButton("➕ Финальный канал", callback_data="add_referral_channel")]
    ]
    
    for channel in sub_channels:
        keyboard.append([InlineKeyboardButton(f"🗑️ Удалить {channel[3]}", callback_data=f"delete_sub_{channel[0]}")])
    
    for channel in ref_channels:
        keyboard.append([InlineKeyboardButton(f"🗑️ Удалить {channel[2]}", callback_data=f"delete_ref_{channel[0]}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")])
    
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
                        await update.message.reply_text(f"✅ Канал {channel_name} добавлен!")
                    else:
                        await update.message.reply_text("❌ Ошибка при добавлении!")
                else:
                    await update.message.reply_text("❌ Неверный формат! Используйте: `@username Название`", parse_mode='Markdown')
                
                context.user_data['awaiting_channel'] = False
                await show_manage_channels(update, context)
                
            elif channel_type == 'private':
                parts = text.split(' ', 1)
                if len(parts) == 2:
                    channel_url = parts[0]
                    channel_name = parts[1]
                    
                    if db.add_subscription_channel(None, channel_url, channel_name, 'private'):
                        await update.message.reply_text(f"✅ Канал {channel_name} добавлен!")
                    else:
                        await update.message.reply_text("❌ Ошибка при добавлении!")
                else:
                    await update.message.reply_text("❌ Неверный формат! Используйте: `ссылка Название`")
                
                context.user_data['awaiting_channel'] = False
                await show_manage_channels(update, context)
                
            elif channel_type == 'referral':
                parts = text.split(' ', 1)
                if len(parts) == 2:
                    channel_url = parts[0]
                    channel_name = parts[1]
                    
                    if db.add_referral_channel(channel_url, channel_name):
                        await update.message.reply_text(f"✅ Финальный канал {channel_name} добавлен!")
                    else:
                        await update.message.reply_text("❌ Ошибка при добавлении!")
                else:
                    await update.message.reply_text("❌ Неверный формат! Используйте: `ссылка Название`")
                
                context.user_data['awaiting_channel'] = False
                await show_manage_channels(update, context)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
            context.user_data['awaiting_channel'] = False

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await show_admin_panel(update, context)
    else:
        await update.message.reply_text("🚫 У вас нет доступа к этой команде")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subscription_status = await check_subscriptions(update, context)
    
    if subscription_status["all_subscribed"]:
        await show_success_message(update, context)
    else:
        await update.message.reply_text("❌ Вы не подписаны на все необходимые каналы!")
        await show_subscription_request(update, context, subscription_status["missing_channels"])

async def set_commands(application: Application):
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("check", "Проверить подписку"),
        BotCommand("admin", "Панель управления")
    ]
    await application.bot.set_my_commands(commands)

def main():
    if db is None:
        logger.error("❌ Не удалось инициализировать базу данных. Бот не может быть запущен.")
        return
        
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("admin", admin_command))
    
    # Обработчики кнопок
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Установка команд бота
    application.post_init = set_commands
    
    # Запуск бота
    logger.info("🚀 Бот запускается...")
    application.run_polling()

if __name__ == "__main__":
    main()
