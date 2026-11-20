"""Barbershop booking bot (aiogram 3).

Flow: service -> date -> time -> confirm. Everything the user picked travels inside the
callback data, so the bot keeps no in-memory state and survives restarts.
"""
import asyncio
import html
import logging
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import config
from db import Database
from logic import available_dates, free_slots
from texts import t

logging.basicConfig(level=logging.INFO)
router = Router()
db = Database(config.DB_PATH)

SCHEDULE = dict(
    start_hour=config.WORK_START,
    end_hour=config.WORK_END,
    step_minutes=config.SLOT_MINUTES,
    buffer_minutes=config.BUFFER_MINUTES,
)
WEEKDAYS = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "uk": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"],
}


# ---------- helpers ----------
def money(amount) -> str:
    return f"{config.CURRENCY}{amount}"


def service_name(key: str) -> str:
    return config.SERVICES[key][config.LANG]


def fmt_day(d: date) -> str:
    return f"{WEEKDAYS[config.LANG][d.weekday()]} {d.day:02d}.{d.month:02d}"


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def who(user) -> tuple:
    """(display name, '@username' or '') of a Telegram user, safe for HTML."""
    name = html.escape(user.full_name or "—")
    username = f"@{user.username}" if user.username else ""
    return name, username


def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text=t("btn_book"))
    kb.button(text=t("btn_my"))
    kb.button(text=t("btn_prices"))
    kb.button(text=t("btn_contacts"))
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


def services_kb():
    kb = InlineKeyboardBuilder()
    for key, s in config.SERVICES.items():
        kb.button(text=f"{s[config.LANG]} — {money(s['price'])}", callback_data=f"svc:{key}")
    kb.adjust(1)
    return kb.as_markup()


# ---------- simple screens ----------
@router.message(CommandStart())
async def cmd_start(m: Message):
    await m.answer(t("start"), reply_markup=main_menu())


@router.message(F.text == t("btn_prices"))
async def show_prices(m: Message):
    lines = [t("prices_title"), ""]
    lines += [f"• {s[config.LANG]} — {money(s['price'])}" for s in config.SERVICES.values()]
    await m.answer("\n".join(lines))


@router.message(F.text == t("btn_contacts"))
async def show_contacts(m: Message):
    await m.answer(t("contacts"))


# ---------- booking flow ----------
@router.message(F.text == t("btn_book"))
async def book_start(m: Message):
    await m.answer(t("choose_service"), reply_markup=services_kb())


@router.callback_query(F.data == "back:services")
async def back_to_services(cb: CallbackQuery):
    await cb.message.edit_text(t("choose_service"), reply_markup=services_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("svc:"))
async def choose_service(cb: CallbackQuery):
    svc = cb.data.split(":")[1]
    dates = available_dates(
        db, datetime.now(), config.DAYS_AHEAD, closed_weekdays=config.CLOSED_WEEKDAYS, **SCHEDULE
    )
    if not dates:
        await cb.message.edit_text(t("no_dates", days=config.DAYS_AHEAD))
        await cb.answer()
        return
    kb = InlineKeyboardBuilder()
    for d in dates:
        kb.button(text=fmt_day(d), callback_data=f"date:{svc}:{d.isoformat()}")
    kb.adjust(2)
    kb.row(InlineKeyboardButton(text=t("btn_back"), callback_data="back:services"))
    await cb.message.edit_text(t("choose_date"), reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("date:"))
async def choose_date(cb: CallbackQuery):
    _, svc, day_iso = cb.data.split(":", 2)
    day = date.fromisoformat(day_iso)
    slots = free_slots(db, day, datetime.now(), **SCHEDULE)
    if not slots:
        await cb.answer(t("no_times"), show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    for s in slots:
        kb.button(text=s, callback_data=f"time:{svc}:{day_iso}:{s}")
    kb.adjust(3)
    kb.row(InlineKeyboardButton(text=t("btn_back"), callback_data=f"svc:{svc}"))
    await cb.message.edit_text(t("choose_time", date=fmt_day(day)), reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("time:"))
async def choose_time(cb: CallbackQuery):
    _, svc, day_iso, time_s = cb.data.split(":", 3)
    kb = InlineKeyboardBuilder()
    kb.button(text=t("btn_confirm"), callback_data=f"ok:{svc}:{day_iso}:{time_s}")
    kb.button(text=t("btn_back"), callback_data=f"date:{svc}:{day_iso}")
    kb.adjust(2)
    text = t(
        "confirm",
        service=service_name(svc),
        date=fmt_day(date.fromisoformat(day_iso)),
        time=time_s,
        price=money(config.SERVICES[svc]["price"]),
    )
    await cb.message.edit_text(text, reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("ok:"))
async def confirm_booking(cb: CallbackQuery):
    _, svc, day_iso, time_s = cb.data.split(":", 3)
    day = date.fromisoformat(day_iso)
    # re-check: the slot may have been taken (or expired) while the user was thinking
    if time_s not in free_slots(db, day, datetime.now(), **SCHEDULE):
        await cb.answer(t("slot_taken"), show_alert=True)
        await choose_date_again(cb, svc, day_iso)
        return
    name, username = who(cb.from_user)
    booking_id = db.add_booking(
        cb.from_user.id, cb.from_user.username, cb.from_user.full_name, svc, day_iso, time_s
    )
    if booking_id is None:  # lost a race with another client
        await cb.answer(t("slot_taken"), show_alert=True)
        await choose_date_again(cb, svc, day_iso)
        return
    await cb.message.edit_text(t("booked", id=booking_id, date=fmt_day(day), time=time_s))
    await cb.answer()
    for admin_id in config.ADMIN_IDS:
        try:
            await cb.bot.send_message(
                admin_id,
                t("admin_new", id=booking_id, name=name, username=username,
                  service=service_name(svc), date=fmt_day(day), time=time_s),
            )
        except Exception:
            logging.exception("Could not notify admin %s", admin_id)


async def choose_date_again(cb: CallbackQuery, svc: str, day_iso: str):
    """Show the free times for the day again after a conflict."""
    day = date.fromisoformat(day_iso)
    slots = free_slots(db, day, datetime.now(), **SCHEDULE)
    if not slots:
        await cb.message.edit_text(t("no_times"), reply_markup=services_kb())
        return
    kb = InlineKeyboardBuilder()
    for s in slots:
        kb.button(text=s, callback_data=f"time:{svc}:{day_iso}:{s}")
    kb.adjust(3)
    await cb.message.edit_text(t("choose_time", date=fmt_day(day)), reply_markup=kb.as_markup())


# ---------- my bookings / cancel ----------
def my_bookings_view(user_id: int):
    rows = db.user_upcoming(user_id, now_str())
    if not rows:
        return t("no_bookings"), None
    kb = InlineKeyboardBuilder()
    lines = [t("my_bookings"), ""]
    for r in rows:
        lines.append(t("booking_line", id=r["id"], date=fmt_day(date.fromisoformat(r["date"])),
                       time=r["time"], service=service_name(r["service"])))
        kb.button(text=t("btn_cancel_booking", id=r["id"]), callback_data=f"cancel:{r['id']}")
    kb.adjust(1)
    return "\n".join(lines), kb.as_markup()


@router.message(F.text == t("btn_my"))
async def my_bookings(m: Message):
    text, kb = my_bookings_view(m.from_user.id)
    await m.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_booking(cb: CallbackQuery):
    booking_id = int(cb.data.split(":")[1])
    booking = db.get_booking(booking_id)
    if not db.cancel(booking_id, user_id=cb.from_user.id):
        await cb.answer(t("cancel_failed"), show_alert=True)
        return
    await cb.answer(t("cancelled", id=booking_id))
    text, kb = my_bookings_view(cb.from_user.id)
    await cb.message.edit_text(text, reply_markup=kb)
    for admin_id in config.ADMIN_IDS:
        try:
            await cb.bot.send_message(
                admin_id,
                t("admin_cancelled", id=booking_id,
                  date=fmt_day(date.fromisoformat(booking["date"])), time=booking["time"]),
            )
        except Exception:
            logging.exception("Could not notify admin %s", admin_id)


# ---------- admin ----------
@router.message(Command("admin"))
async def admin_panel(m: Message):
    if m.from_user.id not in config.ADMIN_IDS:
        await m.answer(t("admin_only"))
        return
    today = date.today()
    for day in (today, today + timedelta(days=1)):
        rows = db.bookings_on(day.isoformat())
        lines = [t("admin_title", date=fmt_day(day)), ""]
        if not rows:
            lines.append(t("admin_empty"))
        for r in rows:
            username = f"@{r['username']}" if r["username"] else ""
            lines.append(t("admin_line", time=r["time"], service=service_name(r["service"]),
                           name=html.escape(r["full_name"] or "—"), username=username))
        await m.answer("\n".join(lines))


# ---------- reminders ----------
async def reminder_loop(bot: Bot):
    """Every minute: remind clients about visits starting within REMINDER_HOURS."""
    while True:
        try:
            now = datetime.now()
            limit = now + timedelta(hours=config.REMINDER_HOURS)
            for b in db.due_reminders(now.strftime("%Y-%m-%d %H:%M"), limit.strftime("%Y-%m-%d %H:%M")):
                try:
                    await bot.send_message(
                        b["user_id"],
                        t("reminder", date=fmt_day(date.fromisoformat(b["date"])),
                          time=b["time"], service=service_name(b["service"])),
                    )
                except Exception:
                    logging.exception("Reminder failed for booking %s", b["id"])
                db.mark_reminded(b["id"])  # mark anyway, so we never spam
        except Exception:
            logging.exception("Reminder loop error")
        await asyncio.sleep(60)


async def main():
    if not config.BOT_TOKEN:
        raise SystemExit("Set BOT_TOKEN in the .env file (see .env.example).")
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    reminders = asyncio.create_task(reminder_loop(bot))  # keep a reference
    try:
        await dp.start_polling(bot)
    finally:
        reminders.cancel()


if __name__ == "__main__":
    asyncio.run(main())
