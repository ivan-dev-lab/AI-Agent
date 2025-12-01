# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery

import aiosqlite

from keyboards import (
    main_menu_kb,
    la_panel_kb,
    student_menu_kb,
    back_kb,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    teacher_main_kb,
)
from utils import ensure_authorized, has_post
from db import consume_pending_la, get_school_by_id, consume_pending_student
from config import DB_PATH
from callbacks import CB_STU_MENU

router = Router()

# --- Главное меню в зависимости от роли ---
async def _show_main_for(user_id: int, target: Message | CallbackQuery):
    if not await ensure_authorized(user_id, target):
        return
    
    # Локальный администратор
    if await has_post(user_id, "local_admin"):
        text = "🏫 <b>Панель локального администратора</b>"
        kb = la_panel_kb()

    # Ученик
    elif await has_post(user_id, "student"):
        text = (
            "👨‍🎓 <b>Меню ученика</b>\n\n"
            "• Посмотреть задания\n"
            "• Посмотреть класс\n"
            "• Учителя школы"
        )
        kb = student_menu_kb()

    # Учитель
    elif await has_post(user_id, "teacher"):
        text = (
            "👩‍🏫 <b>Меню учителя</b>\n\n"
            "Выберите действие."
        )
        kb = teacher_main_kb()
    # По умолчанию — общее меню
    else:
        text = (
            "Вы не авторизованы"
        )
        kb = None

    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb)
    else:
        await target.message.edit_text(text, reply_markup=kb)

def _cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_activation")]
    ])

@router.callback_query(F.data == "cancel_activation")
async def cb_cancel_activation(cq: CallbackQuery):
    await _show_main_for(cq.from_user.id, cq)

@router.message(Command("start"))
async def cmd_start(msg: Message, command: CommandObject):
    arg = command.args  # то, что идёт после /start

    # 1) Приглашение ученика по токену stu_xxx
    if arg and arg.startswith("stu_"):
        token = arg.split("stu_", 1)[1]
        result = await consume_pending_student(token, msg.from_user.id)
        if not result:
            await msg.answer("❌ Приглашение недействительно или уже использовано.")
            return await _show_main_for(msg.from_user.id, msg)

        class_id, display_name = result

        # Получим имя класса для сообщения
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT name FROM classes WHERE id = ?", (class_id,))
            row = await cur.fetchone()
            class_name = row["name"] if row else "неизвестный класс"

        await msg.answer(
            "🎉 <b>Добро пожаловать!</b>\n\n"
            "Вы зарегистрированы как <b>ученик</b>.\n"
            f"👤 Имя в системе: <b>{display_name}</b>\n"
            f"📁 Группа: <b>{class_name}</b>",
            reply_markup=back_kb()
        )
        return

    # 2) Приглашение локального администратора по паролю
    if arg and not arg.startswith("stu_"):
        school_id = await consume_pending_la(msg.from_user.id, arg)
        if not school_id:
            await msg.answer("❌ Приглашение недействительно или уже использовано.")
            return await _show_main_for(msg.from_user.id, msg)

        school = await get_school_by_id(school_id)
        title = school["name"] if school else f"ID {school_id}"

        await msg.answer(
            f"🎉 Вы успешно привязаны как локальный администратор к учебному заведению:\n<b>{title}</b>",
            reply_markup=back_kb()
        )
        return

    # Обычный старт — показываем меню по роли
    await _show_main_for(msg.from_user.id, msg)

@router.callback_query(F.data == "back_to_main")
async def cb_back(cq: CallbackQuery):
    await _show_main_for(cq.from_user.id, cq)

