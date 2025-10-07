# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Tuple

from callbacks import (
    CB_BACK, CB_SETTINGS,
    CB_ADD_TASK, CB_LIST_TASKS, CB_ADD_CLASS, CB_ADD_STUDENT, CB_ENROLL, CB_REGISTER, CB_GEN,
    CB_GA_MENU
)
from callbacks import (
    CB_GA_MENU, CB_GA_SEC_CORE, CB_GA_SEC_MORE, CB_GA_SEC_INFO, CB_BACK,
    CB_GA_ADD_SCHOOL, CB_GA_EDIT_SCHOOLS, CB_GA_ASSIGN_LA, CB_GA_EDIT_LA,
    CB_GA_ASSIGN_TEACHER, CB_GA_ASSIGN_STUDENT, CB_GA_EDIT_TEACHERS, CB_GA_EDIT_STUDENTS,
    CB_GA_LIST_SCHOOLS, CB_GA_LIST_LA, CB_GA_LIST_TEACHERS, CB_GA_LIST_STUDENTS, CB_GA_LIST_GA,
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

def ga_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Панель администратора", callback_data=CB_GA_MENU)],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data=CB_SETTINGS)],
    ])


def ga_panel_kb() -> InlineKeyboardMarkup:
    # три крупные кнопки-раздела
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧱 Основные", callback_data=CB_GA_SEC_CORE)],
        [InlineKeyboardButton(text="🧩 Дополнительные", callback_data=CB_GA_SEC_MORE)],
        [InlineKeyboardButton(text="📚 Информационные", callback_data=CB_GA_SEC_INFO)],
        [InlineKeyboardButton(text="🏁 В главное меню", callback_data=CB_BACK)],
    ])

def ga_core_kb() -> InlineKeyboardMarkup:
    rows = [
        ("🏫 Добавить Учебное заведение", CB_GA_ADD_SCHOOL),
        ("🛠 Редактировать Учебное заведение", CB_GA_EDIT_SCHOOLS),
        ("🧑‍💼 Назначить Локального администратора", CB_GA_ASSIGN_LA),
        ("🧑‍💼 Редактировать Учебное заведение", CB_GA_EDIT_LA),
        ("⬅ Назад к разделам", CB_GA_MENU),
    ]
    return single_col_kb(rows)

def ga_more_kb() -> InlineKeyboardMarkup:
    rows = [
        ("👩‍🏫 Назначить учителя", CB_GA_ASSIGN_TEACHER),
        ("👨‍🎓 Назначить ученика", CB_GA_ASSIGN_STUDENT),
        ("✏️ Редактировать учителей", CB_GA_EDIT_TEACHERS),
        ("✏️ Редактировать учеников", CB_GA_EDIT_STUDENTS),
        ("⬅ Назад к разделам", CB_GA_MENU),
    ]
    return single_col_kb(rows)

def ga_info_kb() -> InlineKeyboardMarkup:
    rows = [
        ("🏫 Список Учебных заведений", CB_GA_LIST_SCHOOLS),
        ("🧑‍💼 Список Локальных администраторов", CB_GA_LIST_LA),
        ("👩‍🏫 Список учителей", CB_GA_LIST_TEACHERS),
        ("👨‍🎓 Список учеников", CB_GA_LIST_STUDENTS),
        ("🛡 Список Глобальных администраторов", CB_GA_LIST_GA),
        ("⬅ Назад к разделам", CB_GA_MENU),
    ]
    return single_col_kb(rows)
