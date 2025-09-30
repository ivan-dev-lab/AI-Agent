# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

import aiosqlite
from config import DB_PATH, DEFAULT_TZ
from keyboards import back_kb
from callbacks import CB_ADD_CLASS

router = Router()

@router.callback_query(F.data == CB_ADD_CLASS)
async def cb_add_class(cq: CallbackQuery):
    from handlers.text import USER_STATE
    USER_STATE[cq.from_user.id] = {"mode": "add_class", "step": 0, "data": {}, "chat_id": cq.message.chat.id}
    await cq.message.edit_text(
        "🏷 <b>Добавление класса</b>\n\n"
        "Шаг 1/1: отправьте <b>название класса</b>.\n\n"
        "Пример: <code>Робототехника-10А</code>\n", reply_markup=back_kb()
    )

@router.message(Command("add_class"))
async def legacy_add_class(msg: Message):
    # поддержка, если вдруг введут командой
    name = msg.text.split(maxsplit=1)[1].strip() if len(msg.text.split(maxsplit=1)) > 1 else None
    if not name:
        return await msg.answer("Использование: /add_class name")
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO classes(name, owner_chat_id, timezone) VALUES (?, ?, ?)",
                (name, msg.chat.id, DEFAULT_TZ)
            )
            await db.commit()
        except Exception as e:
            return await msg.answer(f"Ошибка создания класса: {e}")
    await msg.answer(f"✅ Класс создан: <b>{name}</b> (TZ={DEFAULT_TZ})")
