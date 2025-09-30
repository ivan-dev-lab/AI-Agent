# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from keyboards import main_menu_kb, back_kb
from callbacks import CB_BACK, CB_SETTINGS

router = Router()

def main_menu_text() -> str:
    return (
        "🏁 <b>Главное меню</b>\n\n"
        "Выберите действие. Ввод данных происходит <i>после</i> нажатия кнопки.\n"
        "Таймзона по умолчанию: <b>UTC</b>.\n"
    )

async def show_main_menu(target):
    if isinstance(target, Message):
        await target.answer(main_menu_text(), reply_markup=main_menu_kb())
    else:
        await target.message.edit_text(main_menu_text(), reply_markup=main_menu_kb())

@router.message(Command("start"))
async def cmd_start(msg: Message):
    await show_main_menu(msg)

@router.message(Command("help"))
async def cmd_help(msg: Message):
    await show_main_menu(msg)

@router.callback_query(F.data == CB_BACK)
async def cb_back(cq: CallbackQuery):
    # сброс in-memory FSM (если где-то был)
    from handlers.text import USER_STATE
    USER_STATE.pop(cq.from_user.id, None)
    await show_main_menu(cq)

@router.callback_query(F.data == CB_SETTINGS)
async def cb_settings(cq: CallbackQuery):
    from handlers.text import USER_STATE
    USER_STATE.pop(cq.from_user.id, None)
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        "• Таймзона: пока по умолчанию <b>UTC</b>.\n"
        "• В будущей версии тут можно будет выбрать свою IANA TZ.\n"
    )
    await cq.message.edit_text(text, reply_markup=back_kb())
