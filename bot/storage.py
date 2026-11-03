"""SQLite storage for daily-digest subscriptions.

Synchronous sqlite3 is fine here: tiny table, local file, rare writes.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


class Subscriptions:
    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS subs ("
                "chat_id INTEGER PRIMARY KEY, hhmm TEXT NOT NULL, last_sent TEXT)"
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def set_daily(self, chat_id: int, hhmm: str, now_hhmm: str, today: str) -> None:
        """Subscribe/update. If today's time already passed, skip today's digest."""
        last_sent = today if hhmm <= now_hhmm else None
        with closing(self._conn()) as c, c:
            c.execute(
                "INSERT INTO subs(chat_id, hhmm, last_sent) VALUES (?,?,?) "
                "ON CONFLICT(chat_id) DO UPDATE SET hhmm=excluded.hhmm, last_sent=excluded.last_sent",
                (chat_id, hhmm, last_sent),
            )

    def remove(self, chat_id: int) -> bool:
        with closing(self._conn()) as c, c:
            return c.execute("DELETE FROM subs WHERE chat_id=?", (chat_id,)).rowcount > 0

    def due(self, now_hhmm: str, today: str) -> list[int]:
        """Chats whose time has come today and who have not received today's digest."""
        with closing(self._conn()) as c:
            rows = c.execute(
                "SELECT chat_id FROM subs WHERE hhmm <= ? AND (last_sent IS NULL OR last_sent <> ?)",
                (now_hhmm, today),
            ).fetchall()
        return [r[0] for r in rows]

    def mark_sent(self, chat_id: int, today: str) -> None:
        with closing(self._conn()) as c, c:
            c.execute("UPDATE subs SET last_sent=? WHERE chat_id=?", (today, chat_id))
