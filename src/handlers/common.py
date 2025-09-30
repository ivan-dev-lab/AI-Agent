# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from keyboards import main_menu_kb, ga_main_kb, back_kb
from utils import ensure_authorized, is_global_admin

router = Router()

async def _show_main_for(user_id: int, target):
    """Показывает нужное главное меню в зависимости от роли."""
    if not await ensure_authorized(user_id, target):
        return
    if await is_global_admin(user_id):
        text = (
            "🏁 <b>Главное меню (Глобальный администратор)</b>\n\n"
            "Выберите действие."
        )
        kb = ga_main_kb()
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

@router.message(Command("start", "help"))
async def cmd_start(msg: Message):
    await _show_main_for(msg.from_user.id, msg)

@router.callback_query(F.data == "back_to_main")
async def cb_back(cq: CallbackQuery):
    await _show_main_for(cq.from_user.id, cq)

# Настройки пока заглушка
@router.callback_query(F.data == "settings")
async def cb_settings(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    await cq.message.edit_text(
        "⚙️ <b>Настройки</b>\n\nСкоро тут можно будет выбрать таймзону и другое.",
        reply_markup=back_kb()
    )
