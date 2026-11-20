"""Settings. Values come from the .env file (see .env.example)."""
import os
from pathlib import Path


def _load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
LANG = os.getenv("BOT_LANG", "en")          # "en" or "uk"
DB_PATH = os.getenv("DB_PATH", "bookings.db")
CURRENCY = os.getenv("CURRENCY", "$")

# Working schedule (server local time)
WORK_START = int(os.getenv("WORK_START", "10"))        # first slot starts at 10:00
WORK_END = int(os.getenv("WORK_END", "19"))            # last slot ends at 19:00
SLOT_MINUTES = int(os.getenv("SLOT_MINUTES", "60"))
DAYS_AHEAD = int(os.getenv("DAYS_AHEAD", "7"))
BUFFER_MINUTES = int(os.getenv("BUFFER_MINUTES", "30"))  # can't book less than 30 min ahead
CLOSED_WEEKDAYS = {6}                                   # 0 = Monday ... 6 = Sunday
REMINDER_HOURS = int(os.getenv("REMINDER_HOURS", "24"))  # remind this many hours before

# Services shown to clients
SERVICES = {
    "haircut": {"en": "Haircut", "uk": "Стрижка", "price": 25},
    "beard": {"en": "Beard trim", "uk": "Оформлення бороди", "price": 15},
    "combo": {"en": "Haircut + beard", "uk": "Стрижка + борода", "price": 35},
}

if LANG not in ("en", "uk"):
    LANG = "en"
