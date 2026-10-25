import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import (
    DB_PATH,
    STARTING_COINS,
    STARTING_LEVEL,
    STARTING_XP,
)


# ============================================================
# DATABASE PATH
# ============================================================

DB_DIR = os.path.dirname(DB_PATH)

if DB_DIR:
    os.makedirs(DB_DIR, exist_ok=True)


# ============================================================
# CONNECTION
# ============================================================

def get_connection() -> sqlite3.Connection:
    """Create and return a SQLite database connection."""

    connection = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db() -> None:
    """Create all Solurix database tables."""

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # ----------------------------------------------------
        # USERS
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',

                level INTEGER NOT NULL DEFAULT 1,
                xp INTEGER NOT NULL DEFAULT 0,
                coins INTEGER NOT NULL DEFAULT 100,

                battles INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                hunts INTEGER NOT NULL DEFAULT 0,
                messages INTEGER NOT NULL DEFAULT 0,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # ----------------------------------------------------
        # GROUP MEMBERS
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS group_members (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,

                joined_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                PRIMARY KEY (chat_id, user_id)
            )
            """
        )

        # ----------------------------------------------------
        # COOLDOWNS
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                last_used REAL NOT NULL DEFAULT 0,

                PRIMARY KEY (user_id, action)
            )
            """
        )

        # ----------------------------------------------------
        # GAME HISTORY
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                result TEXT DEFAULT '',
                reward INTEGER NOT NULL DEFAULT 0,

                created_at TEXT NOT NULL
            )
            """
        )

        # ----------------------------------------------------
        # DAILY REWARDS
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_rewards (
                user_id INTEGER PRIMARY KEY,
                last_claim TEXT NOT NULL
            )
            """
        )

        # ----------------------------------------------------
        # WEEKLY REWARDS
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_rewards (
                user_id INTEGER PRIMARY KEY,
                last_claim TEXT NOT NULL
            )
            """
        )

        # ----------------------------------------------------
        # INDEXES
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_group_members_chat
            ON group_members(chat_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_group_members_user
            ON group_members(user_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_user
            ON history(user_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_created
            ON history(created_at)
            """
        )

        connection.commit()

    finally:
        connection.close()


# ============================================================
# TIME HELPERS
# ============================================================

def utc_now() -> str:
    """Return the current UTC time as ISO format."""

    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# USER FUNCTIONS
# ============================================================

def ensure_user(
    user_id: int,
    username: str = "",
    first_name: str = "",
) -> None:
    """
    Create the user if they don't exist.
    Otherwise update their basic information.
    """

    now = utc_now()

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO users (
                user_id,
                username,
                first_name,
                level,
                xp,
                coins,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                username,
                first_name,
                STARTING_LEVEL,
                STARTING_XP,
                STARTING_COINS,
                now,
                now,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def get_user(
    user_id: int,
) -> Optional[Dict[str, Any]]:
    """Return a user as a dictionary."""

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if not row:
            return None

        return dict(row)

    finally:
        connection.close()


# ============================================================
# COINS
# ============================================================

def add_coins(
    user_id: int,
    amount: int,
) -> None:
    """Add or remove coins from a user."""

    ensure_user(user_id)

    connection = get_connection()

    try:
        connection.execute(
            """
            UPDATE users
            SET
                coins = MAX(0, coins + ?),
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                amount,
                utc_now(),
                user_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def get_coins(
    user_id: int,
) -> int:
    """Return user's current coin balance."""

    user = get_user(user_id)

    if not user:
        return 0

    return int(
        user.get("coins", 0)
    )


# ============================================================
# XP
# ============================================================

# ============================================================
# XP
# ============================================================

def add_xp(
    user_id: int,
    amount: int,
) -> None:
    """Add XP and update the user's level."""

    ensure_user(user_id)
    connection = get_connection()

    try:
        connection.execute(
            """
            UPDATE users
            SET xp = MAX(0, xp + ?),
                updated_at = ?
            WHERE user_id = ?
            """,
            (amount, utc_now(), user_id),
        )

        row = connection.execute(
            "SELECT xp FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row:
            new_level = max(1, int(row["xp"]) // 100 + 1)

            connection.execute(
                """
                UPDATE users
                SET level = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (new_level, utc_now(), user_id),
            )

        connection.commit()

    finally:
        connection.close()


# ============================================================
# GAME DATABASE HELPERS
# ============================================================

def increment_stat(user_id: int, stat: str) -> None:
    allowed = {"battles", "wins", "losses", "hunts", "messages"}
    if stat not in allowed:
        raise ValueError(f"Invalid stat: {stat}")

    ensure_user(user_id)
    connection = get_connection()
    try:
        connection.execute(
            f"UPDATE users SET {stat} = {stat} + 1, updated_at = ? WHERE user_id = ?",
            (utc_now(), user_id),
        )
        connection.commit()
    finally:
        connection.close()


def add_history(user_id: int, action: str, result: str = "", reward: int = 0) -> None:
    ensure_user(user_id)
    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO history (user_id, action, result, reward, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, result, reward, utc_now()),
        )
        connection.commit()
    finally:
        connection.close()


def get_cooldown(user_id: int, action: str) -> float:
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT last_used FROM cooldowns WHERE user_id = ? AND action = ?",
            (user_id, action),
        ).fetchone()
        return float(row["last_used"]) if row else 0.0
    finally:
        connection.close()


def set_cooldown(user_id: int, action: str, last_used: float) -> None:
    connection = get_connection()
    try:
        connection.execute(
            """INSERT INTO cooldowns (user_id, action, last_used)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, action)
               DO UPDATE SET last_used = excluded.last_used""",
            (user_id, action, last_used),
        )
        connection.commit()
    finally:
        connection.close()


def add_group_member(chat_id: int, user_id: int) -> None:
    now = utc_now()
    connection = get_connection()
    try:
        connection.execute(
            """INSERT INTO group_members (chat_id, user_id, joined_at, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(chat_id, user_id)
               DO UPDATE SET updated_at = excluded.updated_at""",
            (chat_id, user_id, now, now),
        )
        connection.commit()
    finally:
        connection.close()


def get_group_ranking(chat_id: int, limit: int = 10) -> list:
    connection = get_connection()
    try:
        rows = connection.execute(
            """SELECT u.*
               FROM group_members AS gm
               JOIN users AS u ON u.user_id = gm.user_id
               WHERE gm.chat_id = ?
               ORDER BY u.level DESC, u.xp DESC, u.coins DESC
               LIMIT ?""",
            (chat_id, max(1, limit)),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def set_level(user_id: int, level: int) -> None:
    ensure_user(user_id)
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE users SET level = ?, updated_at = ? WHERE user_id = ?",
            (max(1, level), utc_now(), user_id),
        )
        connection.commit()
    finally:
        connection.close()


def get_last_daily_claim(user_id: int):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT last_claim FROM daily_rewards WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["last_claim"] if row else None
    finally:
        connection.close()


def set_daily_claim(user_id: int) -> None:
    connection = get_connection()
    try:
        connection.execute(
            """INSERT INTO daily_rewards (user_id, last_claim) VALUES (?, ?)
               ON CONFLICT(user_id)
               DO UPDATE SET last_claim = excluded.last_claim""",
            (user_id, utc_now()),
        )
        connection.commit()
    finally:
        connection.close()


def get_last_weekly_claim(user_id: int):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT last_claim FROM weekly_rewards WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["last_claim"] if row else None
    finally:
        connection.close()


def set_weekly_claim(user_id: int) -> None:
    connection = get_connection()
    try:
        connection.execute(
            """INSERT INTO weekly_rewards (user_id, last_claim) VALUES (?, ?)
               ON CONFLICT(user_id)
               DO UPDATE SET last_claim = excluded.last_claim""",
            (user_id, utc_now()),
        )
        connection.commit()
    finally:
        connection.close()


def reset_user(user_id: int) -> None:
    ensure_user(user_id)
    connection = get_connection()
    try:
        connection.execute(
            """UPDATE users SET level = ?, xp = ?, coins = ?,
               battles = 0, wins = 0, losses = 0, hunts = 0,
               messages = 0, updated_at = ? WHERE user_id = ?""",
            (STARTING_LEVEL, STARTING_XP, STARTING_COINS, utc_now(), user_id),
        )
        connection.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM cooldowns WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM daily_rewards WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM weekly_rewards WHERE user_id = ?", (user_id,))
        connection.commit()
    finally:
        connection.close()
