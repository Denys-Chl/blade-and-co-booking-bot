# Barbershop Booking Bot (Telegram, Python, aiogram 3)

A bot where clients book a visit in a few taps: **service → date → time → confirm**.
The owner gets a notification for every new booking, clients get a reminder the day before.

## Features
- Inline-button booking flow; shows only **free** time slots
- **No double bookings**: protected by a database constraint, not only by code
- "My bookings" with one-tap cancellation (only the owner of a booking can cancel it)
- Admin notifications on new and cancelled bookings, `/admin` shows today and tomorrow
- Automatic **reminders** (24 hours before by default)
- Working hours, slot length, closed days and services are set in `config.py`
- Two languages: English and Ukrainian (`BOT_LANG` in `.env`)
- SQLite database, no extra services needed

## Quick start
1. Create a bot in Telegram with [@BotFather](https://t.me/BotFather) and copy the token.
2. Copy `.env.example` to `.env` and fill in `BOT_TOKEN` and `ADMIN_IDS` (your Telegram ID from [@userinfobot](https://t.me/userinfobot)).
3. Install and run:
```bash
pip install -r requirements.txt
python bot.py
```

## Project structure
| File | Purpose |
|---|---|
| `bot.py` | Telegram handlers and the reminder loop |
| `logic.py` | Slot calculation (pure functions, covered by tests) |
| `db.py` | SQLite storage |
| `texts.py` | All messages (EN / UK) |
| `config.py` | Schedule, services, settings |
| `tests/` | Unit tests for the booking logic |

## Run the tests
```bash
python -m unittest discover -s tests -v
```

## Customise
Change services and prices in `config.py` (`SERVICES`), working hours (`WORK_START`, `WORK_END`), and texts in `texts.py`. Times use the server's local timezone.
