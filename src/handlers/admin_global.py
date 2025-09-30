# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import CallbackQuery
from utils import ensure_authorized, is_global_admin
from keyboards import back_kb

from callbacks import CB_GA_MENU

router = Router()

@router.callback_query(F.data == CB_GA_MENU)
async def cb_ga_menu(cq: CallbackQuery):
    # только для глобального админа
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)

    text = (
        "📊 <b>Панель глобального администратора</b>\n\n"
        "Здесь будут разделы: управление пользователями, ролями, аудит, настройки системы и т.п.\n"
        "(пока заглушка) "
    )
    await cq.message.edit_text(text, reply_markup=back_kb())
