import os
import sys
import tempfile
import unittest
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import Database  # noqa: E402
from logic import available_dates, day_slots, free_slots  # noqa: E402

CFG = dict(start_hour=10, end_hour=19, step_minutes=60, buffer_minutes=30)


class BookingTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = Database(self.path)

    def tearDown(self):
        os.remove(self.path)

    def book(self, d="2026-11-23", t="10:00", user=1):
        return self.db.add_booking(user, "u", "User", "haircut", d, t)

    def test_slots_for_future_day(self):
        now = datetime(2026, 11, 21, 12, 0)
        slots = day_slots(date(2026, 11, 23), now, **CFG)
        self.assertEqual(slots[0], "10:00")
        self.assertEqual(slots[-1], "18:00")
        self.assertEqual(len(slots), 9)

    def test_past_and_buffer_slots_are_hidden_today(self):
        now = datetime(2026, 11, 23, 12, 10)  # 12:10 + 30 min buffer -> first slot 13:00
        slots = day_slots(date(2026, 11, 23), now, **CFG)
        self.assertEqual(slots[0], "13:00")

    def test_double_booking_is_impossible(self):
        self.assertIsNotNone(self.book())
        self.assertIsNone(self.book(user=2))

    def test_slot_is_free_again_after_cancel(self):
        bid = self.book()
        self.assertTrue(self.db.cancel(bid, user_id=1))
        self.assertIsNotNone(self.book(user=2))

    def test_only_owner_can_cancel(self):
        bid = self.book(user=1)
        self.assertFalse(self.db.cancel(bid, user_id=999))
        self.assertTrue(self.db.cancel(bid, user_id=1))
        self.assertFalse(self.db.cancel(bid, user_id=1))  # already cancelled

    def test_free_slots_exclude_taken(self):
        self.book(t="11:00")
        now = datetime(2026, 11, 21, 12, 0)
        slots = free_slots(self.db, date(2026, 11, 23), now, **CFG)
        self.assertNotIn("11:00", slots)
        self.assertIn("10:00", slots)

    def test_closed_weekday_is_skipped(self):
        now = datetime(2026, 11, 21, 12, 0)  # Saturday
        dates = available_dates(self.db, now, 3, closed_weekdays={6}, **CFG)
        self.assertNotIn(date(2026, 11, 22), dates)  # Sunday
        self.assertIn(date(2026, 11, 23), dates)

    def test_full_day_disappears_from_dates(self):
        now = datetime(2026, 11, 21, 12, 0)
        for s in day_slots(date(2026, 11, 23), now, **CFG):
            self.book(t=s)
        dates = available_dates(self.db, now, 4, closed_weekdays={6}, **CFG)
        self.assertNotIn(date(2026, 11, 23), dates)

    def test_user_upcoming_and_reminders(self):
        self.book(d="2026-11-22", t="10:00", user=1)
        self.book(d="2026-11-25", t="10:00", user=1)
        up = self.db.user_upcoming(1, "2026-11-21 12:00")
        self.assertEqual(len(up), 2)
        due = self.db.due_reminders("2026-11-21 12:00", "2026-11-22 12:00")
        self.assertEqual([b["date"] for b in due], ["2026-11-22"])
        self.db.mark_reminded(due[0]["id"])
        self.assertEqual(self.db.due_reminders("2026-11-21 12:00", "2026-11-22 12:00"), [])


if __name__ == "__main__":
    unittest.main()
