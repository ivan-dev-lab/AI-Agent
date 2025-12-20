# -*- coding: utf-8 -*-
import re
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

import aiosqlite
from aiogram.types import BufferedInputFile

from config import DB_PATH, DEFAULT_TZINFO, DATETIME_FORMAT

# ---------- Formatting / helpers ----------

def fmt_dt_local(dt_utc: datetime, tz: ZoneInfo) -> str:
    return dt_utc.astimezone(tz).strftime(DATETIME_FORMAT)


def fmt_tz_label(tz: ZoneInfo | None) -> str:
    """
    Возвращает человекочитаемое обозначение часового пояса.
    Для служебных зон вида Etc/GMT-5 выводим UTC+5 вместо сырого ключа.
    """
    if tz is None:
        tz = DEFAULT_TZINFO
    try:
        key = getattr(tz, "key", "") or ""
    except Exception:
        key = ""

    if key.startswith("Etc/GMT") or not key:
        try:
            now = datetime.now(tz)
            offset = tz.utcoffset(now)
            if offset is None:
                return ""
            total_minutes = int(offset.total_seconds() // 60)
            sign = "+" if total_minutes >= 0 else "-"
            total_minutes = abs(total_minutes)
            hours, minutes = divmod(total_minutes, 60)
            if minutes:
                return f"UTC{sign}{hours:02d}:{minutes:02d}"
            return f"UTC{sign}{hours}"
        except Exception:
            return ""

    return key

def extract_code_from_markdown(md: str) -> str:
    fence = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    m = fence.search(md)
    return m.group(1).strip() if m else md.strip()

def display_student(name: str, username: Optional[str]) -> str:
    return f"{name} (@{username})" if username else f"{name} (—)"

def make_py_document(filename: str, code_text: str) -> BufferedInputFile:
    bio = BytesIO()
    bio.write(code_text.encode("utf-8"))
    bio.seek(0)
    return BufferedInputFile(bio.read(), filename=filename)

def parse_utc_hhmm(s: str) -> datetime:
    """Parse datetime string using the default timezone (UTC+5)."""
    return datetime.strptime(s.strip(), DATETIME_FORMAT).replace(tzinfo=DEFAULT_TZINFO)

# ---------- DB helpers ----------

async def _exists(sql: str, params: tuple) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, params)
        row = await cur.fetchone()
        await cur.close()
        return row is not None

async def fetchone(db, sql: str, params=()):
    cur = await db.execute(sql, params)
    row = await cur.fetchone()
    await cur.close()
    return row

async def fetchall(db, sql: str, params=()):
    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    await cur.close()
    return rows

# ---------- Authorization ----------

AUTH_STATE: dict[int, str] = {}


def set_auth_state(user_id: int, state: str) -> None:
    AUTH_STATE[user_id] = state


def pop_auth_state(user_id: int) -> Optional[str]:
    return AUTH_STATE.pop(user_id, None)


def get_auth_state(user_id: int) -> Optional[str]:
    return AUTH_STATE.get(user_id)


async def is_known_user(user_id: int) -> bool:
    """Есть ли пользователь в users (UserID) — любая роль."""
    return await _exists("SELECT 1 FROM users WHERE UserID = ? LIMIT 1", (user_id,))

async def ensure_authorized(user_id: int, target) -> bool:
    """
    Allow access only when the user exists in users.
    Otherwise send a message and return False.
    target - Message or CallbackQuery.
    """
    if await is_known_user(user_id):
        pop_auth_state(user_id)
        return True

    awaiting = get_auth_state(user_id) == 'await_la_password'
    set_auth_state(user_id, 'await_la_password')
    text = (
        "Вы ещё не зарегистрированы. Уже ждём пароль, отправьте его сообщением."
        if awaiting
        else "Вы не зарегистрированы. Введите пароль, чтобы продолжить."
    )
    try:
        await target.answer(text)          # Message
    except AttributeError:
        await target.message.answer(text)  # CallbackQuery
    return False

# ---------- Role control (strict by users.post) ----------

async def has_post(user_id: int, post: str) -> bool:
    """Проверяет, есть ли у пользователя конкретная должность (post) в users."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT 1 FROM users WHERE UserID = ? AND post = ? LIMIT 1",
            (user_id, post)
        )
        row = await cur.fetchone()
        await cur.close()
        return row is not None

async def ensure_role(user_id: int, post: str, target) -> bool:
    """Гарантирует, что у пользователя должность = post; иначе сообщает и возвращает False."""
    if await has_post(user_id, post):
        return True

    text = f"🚫 Доступ запрещён: требуется роль «{post}»."
    try:
        await target.answer(text)          # Message
    except AttributeError:
        await target.message.answer(text)  # CallbackQuery
    return False

# ---------- Convenience wrappers for common roles ----------

async def is_local_admin(user_id: int) -> bool:
    """Проверка по БД: users.post = 'local_admin'."""
    return await has_post(user_id, "local_admin")

async def is_student(user_id: int) -> bool:
    return await has_post(user_id, "student")

async def is_teacher(user_id: int) -> bool:
    return await has_post(user_id, "teacher")
