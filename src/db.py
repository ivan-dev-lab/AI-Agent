# src/db.py
import aiosqlite
from typing import Any, Iterable, Optional
from config import DB_PATH

# ---- базовые утилиты ---------------------------------------------------------
async def fetchone(db, sql: str, params: Iterable[Any] = ()):
    cur = await db.execute(sql, params)
    row = await cur.fetchone()
    await cur.close()
    return row

async def fetchall(db, sql: str, params: Iterable[Any] = ()):
    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    await cur.close()
    return rows

# ---- создание БД --------------------------------------------------------------
async def ensure_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        # чтобы строки были dict-like: row["col"]
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                owner_chat_id INTEGER NOT NULL,
                timezone TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_utc TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                run_at_utc TEXT NOT NULL,
                kind TEXT NOT NULL,
                UNIQUE(task_id, run_at_utc, kind),
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );

            /* Таблица пользователей проекта (учителя/ученики/и т.п.)
               Ваша актуальная схема:
                 UserID INTEGER PRIMARY KEY,
                 name   TEXT,
                 post   TEXT NOT NULL,
                 active INTEGER NOT NULL DEFAULT 0
            */
            CREATE TABLE IF NOT EXISTS users (
                UserID  INTEGER PRIMARY KEY,
                name    TEXT,
                post    TEXT NOT NULL,
                active  INTEGER NOT NULL DEFAULT 0
            );

            /* НОВОЕ: глобальные администраторы — храним только Telegram ID */
            CREATE TABLE IF NOT EXISTS administrators (
                AdminID INTEGER PRIMARY KEY
            );

            /* Привязки ученик<->класс. student_id = users.UserID */
            CREATE TABLE IF NOT EXISTS enrollments (
                student_id INTEGER NOT NULL,
                class_id   INTEGER NOT NULL,
                UNIQUE (student_id, class_id),
                FOREIGN KEY(student_id) REFERENCES users(UserID) ON DELETE CASCADE,
                FOREIGN KEY(class_id)   REFERENCES classes(id)  ON DELETE CASCADE
            );
            """
        )
        await db.commit()

# ---- авторизация/роли ---------------------------------------------------------
async def is_global_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await fetchone(db, "SELECT 1 FROM administrators WHERE telegram_id=?", (user_id,))
        return row is not None

async def is_known_user(user_id: int) -> bool:
    """Есть ли пользователь в users или administrators."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        r1 = await fetchone(db, "SELECT 1 FROM users WHERE UserID=?", (user_id,))
        if r1:
            return True
        r2 = await fetchone(db, "SELECT 1 FROM administrators WHERE telegram_id=?", (user_id,))
        return r2 is not None
