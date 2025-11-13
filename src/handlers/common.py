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
from db import consume_pending_la, get_school_by_id
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
    # если есть аргумент (например, приглашение ЛА) — логика остаётся,
    # в конце всё равно выводим меню по роли
    arg = command.args
    if arg and arg.isdigit():
        target_user_id = int(arg)
        if target_user_id != msg.from_user.id:
            await msg.answer("❌ Вы не тот пользователь.\nЭто приглашение предназначено для другого аккаунта.")
            return

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

        # передача управления FSM для активации ЛА — без изменений
        from handlers.admin_global import COMMON_STATE
        COMMON_STATE[msg.from_user.id] = {"mode": "await_la_password"}
        await msg.answer(
            "🔐 Обнаружено приглашение!\nПожалуйста, введите <b>пароль</b>, полученный от глобального администратора:",
            reply_markup=_cancel_kb()
        )
        return

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
