import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# === НАСТРОЙКИ (БЕЗ ПРОВЕРОК!) ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")
DB_PATH = "/tmp/bot.db"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS confirmed_subscriptions (
                user_id INTEGER,
                channel_id INTEGER,
                confirmed BOOLEAN DEFAULT FALSE,
                confirmed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, channel_id)
            )
        ''')
        
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
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления пользователя: {e}")
            return False

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

# Инициализация базы данных
try:
    db = Database(DB_PATH)
    logger.info("✅ База данных загружена")
except Exception as e:
    logger.error(f"❌ Критическая ошибка БД: {e}")
    db = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if db is None:
        await update.message.reply_text("🚫 Сервис временно недоступен")
        return
        
    user = update.effective_user
    db.add_user(user.id, user.username, user.full_name)
    await update.message.reply_text("👋 Привет! Бот работает! 🎉")

async def set_commands(application: Application):
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("check", "Проверить подписку")
    ]
    await application.bot.set_my_commands(commands)

def main():
    # === ПРОВЕРКА ПЕРЕМЕННЫХ ТОЛЬКО ЗДЕСЬ! ===
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден! Добавьте в Railway Variables")
        return
        
    if not ADMIN_ID:
        logger.error("❌ ADMIN_ID не найден! Добавьте в Railway Variables")
        return
        
    try:
        ADMIN_ID_int = int(ADMIN_ID)
    except ValueError:
        logger.error("❌ ADMIN_ID должен быть числом!")
        return

    if db is None:
        logger.error("❌ Не удалось инициализировать базу данных.")
        return
        
    logger.info(f"✅ Бот запускается с ADMIN_ID: {ADMIN_ID_int}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    
    # Установка команд бота
    application.post_init = set_commands
    
    # Запуск бота
    logger.info("🚀 Бот запускается...")
    application.run_polling()

if __name__ == "__main__":
    main()
