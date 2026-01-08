import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_TELEGRAM_BOT_TOKEN_AICI")
DB_PATH = os.getenv("DB_PATH", "barbershop.db")

# Setări de lucru
DEFAULT_SLOTS = [
    "10:00", "11:00", "12:00",
    "13:00", "14:00", "15:00",
    "16:00", "17:00", "18:00"
]
