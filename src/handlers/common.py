# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery
import aiosqlite

from keyboards import (
    main_menu_kb,
    ga_main_kb,
    la_panel_kb,        # 👈 добавили меню локального админа
    student_menu_kb,
    back_kb,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from utils import ensure_authorized, is_global_admin, has_post
from db import consume_pending_la, get_school_by_id, consume_pending_student
from config import DB_PATH


from callbacks import CB_STU_MENU

router = Router()

# --- Главный рендер меню по роли ---

async def _show_main_for(user_id: int, target):
    if not await ensure_authorized(user_id, target):
        return

    # Глобальный админ
    if await is_global_admin(user_id):
        text = "🏁 <b>Главное меню (Глобальный администратор)</b>\n\nВыберите действие."
        kb = ga_main_kb()

    # Локальный админ (жёстко по users.post)
    elif await has_post(user_id, "local_admin"):
        text = "🧩 <b>Меню локального администратора</b>"
        kb = la_panel_kb()

    # Ученик (жёстко по users.post)
    elif await has_post(user_id, "student"):
        text = "🎓 <b>Меню ученика</b>"
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

    # 1️⃣ Приглашение локального администратора (числовой код)
    if arg and arg.isdigit():
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

    # 2️⃣ Приглашение ученика по токену stu_xxx
    elif arg and arg.startswith("stu_"):
        # Активация приглашения ученика по токену
        token = arg.split("stu_", 1)[1]
        result = await consume_pending_student(token, msg.from_user.id)
        if not result:
            await msg.answer("❌ Приглашение недействительно или уже использовано.")
            return await _show_main_for(msg.from_user.id, msg)

        class_id, display_name = result

        # Получаем имя класса
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

    # 3️⃣ Обычный /start без спец.параметров — просто показываем главное меню
    await _show_main_for(msg.from_user.id, msg)


    # обычный старт — показываем меню по роли
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
