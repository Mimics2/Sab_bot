import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация - ЗАПОЛНИТЕ СВОИ ДАННЫЕ!
BOT_TOKEN = "7557745613:AAFTpWsCJ2bZMqD6GDwTynnqA8Nc-mRF1Rs"
ADMIN_IDS = [6646433980]  # Ваш Telegram ID

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# База данных SQLite
def init_db():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            name TEXT,
            invite_link TEXT,
            is_private BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Состояния для добавления канала
class AddChannel(StatesGroup):
    waiting_chat_id = State()
    waiting_invite_link = State()

# ===== ОСНОВНЫЕ КОМАНДЫ =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🤖 Я бот для проверки подписок!\n"
        "📊 Статистика: /stats\n"
        "⚙️ Админ-панель: /admin"
    )

# ===== АДМИН-ПАНЕЛЬ =====
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещен")
        return
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel")],
        [types.InlineKeyboardButton(text="🗑 Удалить канал", callback_data="remove_channel")],
        [types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ])
    await message.answer("👨‍💻 Админ-панель:", reply_markup=keyboard)

# Добавление канала
@dp.callback_query(F.data == "add_channel")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddChannel.waiting_chat_id)
    await callback.message.answer(
        "Введите ID канала (например: -1001234567890):\n"
        "💡 Как получить ID? Добавьте @username_to_id_bot в канал"
    )

@dp.message(AddChannel.waiting_chat_id)
async def add_channel_chat_id(message: types.Message, state: FSMContext):
    await state.update_data(chat_id=message.text)
    await state.set_state(AddChannel.waiting_invite_link)
    await message.answer("Теперь отправьте ссылку-приглашение:")

@dp.message(AddChannel.waiting_invite_link)
async def add_channel_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO channels (chat_id, invite_link) VALUES (?, ?)",
            (data['chat_id'], message.text)
        )
        conn.commit()
        await message.answer("✅ Канал успешно добавлен!")
    except sqlite3.IntegrityError:
        await message.answer("❌ Канал с таким ID уже существует")
    finally:
        conn.close()
    
    await state.clear()

# Удаление канала
@dp.callback_query(F.data == "remove_channel")
async def remove_channel_list(callback: types.CallbackQuery):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, invite_link FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    if not channels:
        await callback.message.answer("📭 Список каналов пуст")
        return
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[])
    for chat_id, invite_link in channels:
        keyboard.inline_keyboard.append([
            types.InlineKeyboardButton(
                text=f"❌ {invite_link[:20]}...", 
                callback_data=f"delete_{chat_id}"
            )
        ])
    
    await callback.message.answer("Выберите канал для удаления:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("delete_"))
async def remove_channel_confirm(callback: types.CallbackQuery):
    chat_id = callback.data.replace("delete_", "")
    
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()
    
    await callback.message.answer("✅ Канал удален")
    await callback.answer()

# ===== ПРОВЕРКА ПОДПИСКИ =====
async def check_subscription(user_id: int, channel_chat_id: str) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id=channel_chat_id, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, invite_link FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    if not channels:
        await message.answer("📭 Каналы для проверки не настроены")
        return
    
    not_subscribed = []
    for channel_chat_id, invite_link in channels:
        if not await check_subscription(user_id, channel_chat_id):
            not_subscribed.append(invite_link)
    
    if not_subscribed:
        channels_text = "\n".join([f"🔗 {link}" for link in not_subscribed])
        await message.answer(
            f"❌ Вы не подписаны на каналы:\n\n{channels_text}\n\n"
            f"Подпишитесь и повторите проверку: /check"
        )
    else:
        await message.answer("✅ Вы подписаны на все каналы!")

# ===== СТАТИСТИКА =====
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    # Количество каналов
    cursor.execute("SELECT COUNT(*) FROM channels")
    channels_count = cursor.fetchone()[0]
    
    conn.close()
    
    await message.answer(
        f"📊 Статистика бота:\n"
        f"• Каналов в базе: {channels_count}\n"
        f"• Проверить подписку: /check"
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен")
        return
    
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM channels")
    channels_count = cursor.fetchone()[0]
    conn.close()
    
    await callback.message.answer(
        f"👨‍💻 Админ статистика:\n"
        f"• Каналов в базе: {channels_count}\n"
        f"• Пользователей: ~ (не отслеживается)"
    )

# ===== ЗАПУСК БОТА =====
async def main():
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
