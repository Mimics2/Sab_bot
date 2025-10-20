import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '7557745613:AAFTpWsCJ2bZMqD6GDwTynnqA8Nc-mRF1Rs')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '6646433980').split(',')]

# Настройки базы данных
DATABASE_URL = "sqlite:///bot.db"
