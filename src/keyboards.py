# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Tuple

from callbacks import (
    CB_BACK, CB_SETTINGS,
    CB_ADD_TASK, CB_LIST_TASKS, CB_ADD_CLASS, CB_ADD_STUDENT, CB_ENROLL, CB_REGISTER, CB_GEN,
    CB_GA_MENU
)

def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад в главное меню", callback_data=CB_BACK)]
    ])

def single_col_kb(rows: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=cb)] for t, cb in rows])

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить задание", callback_data=CB_ADD_TASK)],
        [InlineKeyboardButton(text="📋 Список заданий", callback_data=CB_LIST_TASKS)],
        [InlineKeyboardButton(text="🏷 Добавить класс", callback_data=CB_ADD_CLASS)],
        [InlineKeyboardButton(text="👤 Добавить ученика", callback_data=CB_ADD_STUDENT)],
        [InlineKeyboardButton(text="🔗 Записать ученика в класс", callback_data=CB_ENROLL)],
        [InlineKeyboardButton(text="💬 Привязать чат ученика", callback_data=CB_REGISTER)],
        [InlineKeyboardButton(text="🤖 Сгенерировать код (описанием)", callback_data=CB_GEN)],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data=CB_SETTINGS)],
    ])

# ---- Меню для глобального администратора ----
def ga_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Панель администратора", callback_data=CB_GA_MENU)],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data=CB_SETTINGS)],
        [InlineKeyboardButton(text="⬅ Обычное меню", callback_data=CB_BACK)],
    ])
