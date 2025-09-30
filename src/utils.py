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

# ---------- Authorization helpers ----------

async def is_global_admin(user_id: int) -> bool:
    """Проверяет, есть ли user_id в таблице administrators (единственная колонка id)."""
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchone("SELECT 1 FROM administrators WHERE id = ? LIMIT 1", (user_id,))
        return bool(row)

async def is_known_user(user_id: int) -> bool:
    """Проверяет, есть ли user_id в таблице users (UserID — это Telegram ID, без AUTOINCREMENT)."""
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchone("SELECT 1 FROM users WHERE UserID = ? LIMIT 1", (user_id,))
        return bool(row)

async def ensure_authorized(user_id: int, target) -> bool:
    """Если пользователь ни в administrators, ни в users — шлём 'не авторизован' и возвращаем False.
    target — Message или CallbackQuery.
    """
    if await is_global_admin(user_id) or await is_known_user(user_id):
        return True

    text = "🚫 Вы не авторизованы. Обратитесь к администратору."
    # Пустое сообщение без кнопок — как просили
    if hasattr(target, "answer"):
        await target.answer(text)
    else:
        # CallbackQuery
        await target.message.answer(text)
    return False
