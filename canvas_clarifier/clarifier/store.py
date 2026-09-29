"""SQLite state: item ↔ SP task mapping, last-seen due dates, alert history."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    key TEXT PRIMARY KEY,
    sp_task_id TEXT,
    due TEXT,
    title TEXT,
    category TEXT,
    first_seen TEXT,
    last_seen TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    key TEXT,
    condition TEXT,
    message TEXT,
    active INTEGER,
    first_seen TEXT,
    last_seen TEXT,
    PRIMARY KEY (key, condition)
);
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY,
    first_seen TEXT
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


class Store:
    def __init__(self, path: Path | str):
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # items -------------------------------------------------------------
    def item(self, key: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM items WHERE key=?", (key,)).fetchone()

    def items_with_tasks(self) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM items WHERE sp_task_id IS NOT NULL").fetchall()

    def upsert_item(self, key: str, *, now: str, due: str | None, title: str,
                    category: str, sp_task_id: str | None = None) -> None:
        row = self.item(key)
        if row is None:
            self.db.execute(
                "INSERT INTO items (key, sp_task_id, due, title, category, first_seen, last_seen)"
                " VALUES (?,?,?,?,?,?,?)", (key, sp_task_id, due, title, category, now, now))
        else:
            self.db.execute(
                "UPDATE items SET due=?, title=?, category=?, last_seen=?,"
                " sp_task_id=COALESCE(?, sp_task_id) WHERE key=?",
                (due, title, category, now, sp_task_id, key))

    # alerts ------------------------------------------------------------
    def sync_alerts(self, current: dict[tuple[str, str], str], now: str) -> list[tuple[str, str, str]]:
        """Record this run's conditions; return the ones that are new or reappeared."""
        fresh = []
        for (key, cond), msg in current.items():
            row = self.db.execute("SELECT active FROM alerts WHERE key=? AND condition=?",
                                  (key, cond)).fetchone()
            if row is None:
                self.db.execute("INSERT INTO alerts VALUES (?,?,?,?,?,?)",
                                (key, cond, msg, 1, now, now))
                fresh.append((key, cond, msg))
            else:
                if not row["active"]:
                    fresh.append((key, cond, msg))
                self.db.execute("UPDATE alerts SET active=1, message=?, last_seen=?"
                                " WHERE key=? AND condition=?", (msg, now, key, cond))
        for row in self.db.execute("SELECT key, condition FROM alerts WHERE active=1").fetchall():
            if (row["key"], row["condition"]) not in current:
                self.db.execute("UPDATE alerts SET active=0 WHERE key=? AND condition=?",
                                (row["key"], row["condition"]))
        return fresh

    def active_alerts(self) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT key, condition, message, first_seen FROM alerts WHERE active=1"
            " ORDER BY first_seen")]

    # announcements -----------------------------------------------------
    def new_announcement(self, ann_id: int, now: str) -> bool:
        if self.db.execute("SELECT 1 FROM announcements WHERE id=?", (ann_id,)).fetchone():
            return False
        self.db.execute("INSERT INTO announcements VALUES (?,?)", (ann_id, now))
        return True

    # meta --------------------------------------------------------------
    def get_meta(self, k: str) -> str | None:
        row = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return row["v"] if row else None

    def set_meta(self, k: str, v: str) -> None:
        self.db.execute("INSERT INTO meta VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                        (k, v))

    def commit(self) -> None:
        self.db.commit()
