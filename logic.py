"""Slot calculation. Pure functions: easy to test, no Telegram code here."""
from datetime import date, datetime, timedelta


def day_slots(day: date, now: datetime, start_hour: int, end_hour: int,
              step_minutes: int, buffer_minutes: int = 30) -> list:
    """All bookable start times for a day, e.g. ['10:00', '11:00', ...].
    Past times (and times closer than buffer_minutes) are skipped."""
    cur = datetime.combine(day, datetime.min.time()).replace(hour=start_hour)
    end = datetime.combine(day, datetime.min.time()).replace(hour=end_hour)
    earliest = now + timedelta(minutes=buffer_minutes)
    slots = []
    while cur + timedelta(minutes=step_minutes) <= end:
        if cur >= earliest:
            slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_minutes)
    return slots


def free_slots(db, day: date, now: datetime, **cfg) -> list:
    taken = db.taken_times(day.isoformat())
    return [s for s in day_slots(day, now, **cfg) if s not in taken]


def available_dates(db, now: datetime, days_ahead: int, closed_weekdays=(), **cfg) -> list:
    """Dates (starting today) that still have at least one free slot."""
    result = []
    for i in range(days_ahead):
        day = (now + timedelta(days=i)).date()
        if day.weekday() in closed_weekdays:
            continue
        if free_slots(db, day, now, **cfg):
            result.append(day)
    return result
