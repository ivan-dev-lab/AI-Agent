# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery
from typing import Optional

from keyboards import main_menu_kb, ga_main_kb, back_kb, InlineKeyboardMarkup, InlineKeyboardButton
from utils import ensure_authorized, is_global_admin
from db import consume_pending_la, get_school_by_id
from db import consume_pending_la, get_school_by_id, consume_pending_student
from config import DB_PATH
import aiosqlite

from keyboards import main_menu_kb, ga_main_kb, back_kb, InlineKeyboardMarkup, InlineKeyboardButton, student_menu_kb, teacher_main_kb
from utils import ensure_authorized, is_global_admin
from utils import has_post
from callbacks import CB_STU_MENU


router = Router()

async def _show_main_for(user_id: int, target):
    if not await ensure_authorized(user_id, target):
        return

    if await is_global_admin(user_id):
        text = (
            "🏁 <b>Главное меню (Глобальный администратор)</b>\n\n"
            "Выберите действие."
        )
        kb = ga_main_kb()
    elif await has_post(user_id, "student"):  # <-- новая ветка
        text = "🎓 <b>Меню ученика</b>"
        kb = student_menu_kb()
    elif await has_post(user_id, "teacher"):
        text = (
            "👩‍🏫 <b>Меню учителя</b>\n\n"
            "Выберите действие."
        )
        kb = teacher_main_kb()
    else:
        text = (
            "🏁 <b>Главное меню</b>\n\n"
            "Выберите действие. Ввод данных происходит <i>после</i> нажатия кнопки.\n"
            "Таймзона по умолчанию: <b>UTC</b>."
        )
        kb = main_menu_kb()

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
    # FSM для активации ЛА теперь будет в admin_global.py
    await _show_main_for(cq.from_user.id, cq)


@router.message(Command("start"))
async def cmd_start(msg: Message, command: CommandObject):
    arg = command.args

    if arg and arg.isdigit():
        target_user_id = int(arg)
        if target_user_id != msg.from_user.id:
            await msg.answer(
                "❌ Вы не тот пользователь.\n"
                "Это приглашение предназначено для другого аккаунта."
            )
            return

        # Проверка наличия приглашения
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT 1 FROM pending_local_admins WHERE user_id = ?", (target_user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                await msg.answer("❌ Для вас нет активного приглашения.")
                await _show_main_for(msg.from_user.id, msg)
                return

        # === ПЕРЕДАЁМ УПРАВЛЕНИЕ В ADMIN_GLOBAL.PY через FSM ===
        from handlers.admin_global import COMMON_STATE
        COMMON_STATE[msg.from_user.id] = {"mode": "await_la_password"}
        await msg.answer(
            "🔐 Обнаружено приглашение!\n"
            "Пожалуйста, введите <b>пароль</b>, полученный от глобального администратора:",
            reply_markup=_cancel_kb()
        )
        return
    elif arg and arg.startswith("stu_"):
        # Активация приглашения ученика по токену
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
            f"📁 Группа: <b>{class_name}</b>"
        )
    return await _show_main_for(msg.from_user.id, msg)



@router.message(Command("help"))
async def cmd_help(msg: Message):
    await _show_main_for(msg.from_user.id, msg)


# УДАЛЁН: @router.message(F.text) — перенесён в admin_global.py


@router.callback_query(F.data == "back_to_main")
async def cb_back(cq: CallbackQuery):
    await _show_main_for(cq.from_user.id, cq)


@router.callback_query(F.data == "settings")
async def cb_settings(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    await cq.message.edit_text(
        "⚙️ <b>Настройки</b>\n\nСкоро тут можно будет выбрать таймзону и другое.",
        reply_markup=back_kb()
    )