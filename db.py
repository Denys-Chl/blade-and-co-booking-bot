"""SQLite storage for bookings (standard library only)."""
import sqlite3
from contextlib import closing


class Database:
    def __init__(self, path: str):
        self.path = path
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with closing(self._conn()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS bookings (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    username   TEXT,
                    full_name  TEXT,
                    service    TEXT NOT NULL,
                    date       TEXT NOT NULL,      -- YYYY-MM-DD
                    time       TEXT NOT NULL,      -- HH:MM
                    status     TEXT NOT NULL DEFAULT 'active',
                    reminded   INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                -- one active booking per time slot: protects from double booking
                CREATE UNIQUE INDEX IF NOT EXISTS ux_active_slot
                    ON bookings(date, time) WHERE status = 'active';
                """
            )

    def add_booking(self, user_id, username, full_name, service, date, time):
        """Returns the new booking id, or None if the slot is already taken."""
        try:
            with closing(self._conn()) as conn, conn:
                cur = conn.execute(
                    "INSERT INTO bookings (user_id, username, full_name, service, date, time)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, username, full_name, service, date, time),
                )
                return cur.lastrowid
        except sqlite3.IntegrityError:
            return None

    def taken_times(self, date: str) -> set:
        with closing(self._conn()) as conn:
            rows = conn.execute(
                "SELECT time FROM bookings WHERE date = ? AND status = 'active'", (date,)
            ).fetchall()
        return {r["time"] for r in rows}

    def get_booking(self, booking_id: int):
        with closing(self._conn()) as conn:
            return conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()

    def user_upcoming(self, user_id: int, now_str: str):
        """now_str format: 'YYYY-MM-DD HH:MM'."""
        with closing(self._conn()) as conn:
            return conn.execute(
                "SELECT * FROM bookings WHERE user_id = ? AND status = 'active'"
                " AND date || ' ' || time >= ? ORDER BY date, time",
                (user_id, now_str),
            ).fetchall()

    def cancel(self, booking_id: int, user_id=None) -> bool:
        """Cancels an active booking. If user_id is given, only the owner can cancel."""
        sql = "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND status = 'active'"
        params = [booking_id]
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        with closing(self._conn()) as conn, conn:
            return conn.execute(sql, params).rowcount > 0

    def bookings_on(self, date: str):
        with closing(self._conn()) as conn:
            return conn.execute(
                "SELECT * FROM bookings WHERE date = ? AND status = 'active' ORDER BY time",
                (date,),
            ).fetchall()

    def due_reminders(self, now_str: str, limit_str: str):
        """Active, not yet reminded bookings that start between now and limit."""
        with closing(self._conn()) as conn:
            return conn.execute(
                "SELECT * FROM bookings WHERE status = 'active' AND reminded = 0"
                " AND date || ' ' || time > ? AND date || ' ' || time <= ?",
                (now_str, limit_str),
            ).fetchall()

    def mark_reminded(self, booking_id: int) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute("UPDATE bookings SET reminded = 1 WHERE id = ?", (booking_id,))
