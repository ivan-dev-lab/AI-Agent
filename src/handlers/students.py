# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
import aiosqlite

from config import DB_PATH
from keyboards import back_kb, single_col_kb
from callbacks import (
    CB_ADD_STUDENT, CB_REGISTER,
    CB_STU_AFTER_ADD_SKIP, CB_ENROLL_PICK_CLS
)
from utils import display_student

router = Router()

@router.callback_query(F.data == CB_ADD_STUDENT)
async def cb_add_student(cq: CallbackQuery):
    from handlers.text import USER_STATE
    USER_STATE[cq.from_user.id] = {"mode": "add_student", "step": 0, "data": {}, "chat_id": cq.message.chat.id}
    await cq.message.edit_text(
        "👤 <b>Добавление ученика</b>\n\n"
        "Шаг 1/2: отправьте <b>имя ученика</b>.\n", reply_markup=back_kb()
    )

@router.callback_query(F.data == CB_REGISTER)
async def cb_register(cq: CallbackQuery):
    from handlers.text import USER_STATE
    USER_STATE[cq.from_user.id] = {"mode": "register", "step": 0, "data": {}, "chat_id": cq.message.chat.id}
    await cq.message.edit_text(
        "💬 <b>Привязать чат ученика</b>\n\n"
        "Шаг 1/1: отправьте <b>имя ученика</b> для привязки к этому чату.\n", reply_markup=back_kb()
    )

# опциональный коллбэк если понадобится: после добавления ученика снова показать классы
@router.callback_query(F.data == CB_STU_AFTER_ADD_SKIP)
async def cb_stu_after_add_skip(cq: CallbackQuery):
    await cq.message.edit_text("Ок, пропускаем. Что дальше?", reply_markup=back_kb())
