# -*- coding: utf-8 -*-
import re
from io import BytesIO
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional

import aiosqlite
from aiogram.types import BufferedInputFile

from config import DB_PATH



# ---------- Formatting / helpers ----------

def fmt_dt_local(dt_utc: datetime, tz: ZoneInfo) -> str:
    return dt_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M")

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
    """'YYYY-MM-DD HH:MM' -> aware UTC datetime"""
    return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)

# ---------- DB helpers ----------

async def _exists(sql: str, params: tuple) -> bool:
    """Возвращает True, если SELECT что-то нашёл."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, params)
        row = await cur.fetchone()
        await cur.close()
        return row is not None

# ---------- Authorization helpers ----------
# ---------- Local admin helpers ----------
LOCAL_ADMINS = [123456789]  # Замените на реальные ID

def is_local_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь локальным админом."""
    return user_id in LOCAL_ADMINS


async def is_global_admin(user_id: int) -> bool:
    """Проверяет наличие пользователя в таблице administrators (AdminID)."""
    return await _exists(
        "SELECT 1 FROM administrators WHERE AdminID = ? LIMIT 1",
        (user_id,)
    )

async def is_known_user(user_id: int) -> bool:
    """Проверяет наличие пользователя в таблице users (UserID)."""
    return await _exists(
        "SELECT 1 FROM users WHERE UserID = ? LIMIT 1",
        (user_id,)
    )

async def ensure_authorized(user_id: int, target) -> bool:
    """
    Если пользователя нет ни в administrators, ни в users —
    отправляем лаконичное сообщение без кнопок и возвращаем False.
    target — Message или CallbackQuery.
    """
    if await is_global_admin(user_id) or await is_known_user(user_id):
        return True

    text = "🚫 Вы не авторизованы. Обратитесь к администратору."
    try:
        # Message
        await target.answer(text)
    except AttributeError:
        # CallbackQuery
        await target.message.answer(text)
    return False

async def has_post(user_id: int, post: str) -> bool:
    """Есть ли у пользователя конкретная роль (post) в таблице users."""
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
    """
    Гарантирует, что у пользователя заданная роль.
    Если роли нет — отправляет сообщение и возвращает False.
    target — Message или CallbackQuery.
    """
    if await has_post(user_id, post):
        return True

    text = "🚫 Доступ запрещён: требуется роль «{0}».".format(post)
    print(post)
    try:
        await target.answer(text)            # Message
    except AttributeError:
        await target.message.answer(text)    # CallbackQuery
    return False

async def has_post(user_id: int, post: str) -> bool:
    """Есть ли у пользователя конкретная роль (post) в таблице users."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT 1 FROM users WHERE UserID = ? AND post = ? LIMIT 1",
            (user_id, post)
        )
        row = await cur.fetchone()
        print(row)
        await cur.close()
        return row is not None


