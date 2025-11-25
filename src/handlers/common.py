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

from keyboards import (
    main_menu_kb,
    ga_main_kb,
    la_panel_kb,        # 👈 добавили меню локального админа
    student_menu_kb,
    back_kb,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    teacher_main_kb
)
from utils import ensure_authorized, is_global_admin, has_post
from db import consume_pending_la, get_school_by_id, consume_pending_student
from config import DB_PATH


from callbacks import CB_STU_MENU

router = Router()

# --- Главное меню в зависимости от роли ---
async def _show_main_for(user_id: int, target: Message | CallbackQuery):
    # Глобальный администратор
    if await is_global_admin(user_id):
        text = "🛠️ <b>Панель глобального администратора</b>"
        kb = ga_main_kb()

    # Локальный администратор
    elif await has_post(user_id, "local_admin"):
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

    # Учитель (если нужно — сделайте отдельную клавиатуру)
    elif await has_post(user_id, "teacher"):
        text = "👨‍🏫 <b>Меню учителя</b>\n\n(раздел в разработке)"
        kb = back_kb()

    # По умолчанию — общее меню
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

    # 2) Приглашение локального администратора по ПАРОЛЮ (новые ссылки)
    if arg and not arg.startswith("stu_"):
        # Совместимость со старыми ссылками: start=<ваш_telegram_id>
        if arg.isdigit() and int(arg) == msg.from_user.id:
            try:
                # Отдаём управление FSM в admin_global
                from handlers.admin_global import COMMON_STATE
                COMMON_STATE[msg.from_user.id] = {"mode": "await_la_password"}
                await msg.answer("Введите пароль из приглашения локального администратора:", reply_markup=back_kb())
                return
            except Exception:
                pass

        # Пытаемся активировать по паролю
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

@router.callback_query(F.data == "settings")
async def cb_settings(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    await cq.message.edit_text(
        "⚙️ <b>Настройки</b>\n\nСкоро тут можно будет выбрать таймзону и другое.",
        reply_markup=back_kb()
    )
