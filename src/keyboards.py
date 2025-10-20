# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Tuple
from aiogram.utils.keyboard import InlineKeyboardBuilder
from callbacks import StudentCB, TaskCB


from callbacks import (
    CB_BACK, CB_SETTINGS,
    CB_ADD_TASK, CB_LIST_TASKS, CB_ADD_CLASS, CB_ADD_STUDENT, CB_ENROLL, CB_REGISTER, CB_GEN,
    CB_GA_MENU
)
from callbacks import (
    CB_GA_MENU, CB_GA_SEC_CORE, CB_GA_SEC_MORE, CB_GA_SEC_INFO, CB_BACK,
    CB_GA_ADD_SCHOOL, CB_GA_EDIT_SCHOOLS, CB_GA_ASSIGN_LA, CB_GA_EDIT_LA,
    CB_GA_ASSIGN_TEACHER, CB_GA_ASSIGN_STUDENT, CB_GA_EDIT_TEACHERS, CB_GA_EDIT_STUDENTS,
    CB_GA_LIST_SCHOOLS, CB_GA_LIST_LA, CB_GA_LIST_TEACHERS, CB_GA_LIST_STUDENTS, CB_GA_LIST_GA, CB_STU_TASKS, CB_STU_TASKS, CB_STU_TEACHERS, CB_STU_GROUPS, CB_STU_SCHEDULE, CB_STU_INFO,
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
        ("🧑‍💼 Редактировать локальных администраторов", CB_GA_EDIT_LA),
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

# === GA: клавиатура редактирования конкретного УЗ ===
from callbacks import (
    CB_GA_EDIT_SCHOOLS,
    CB_GA_ED_S_NAME, CB_GA_ED_S_SHORT, CB_GA_ED_S_ADDR, CB_GA_ED_S_TZ
)

def ga_edit_school_detail_kb(school_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"{CB_GA_ED_S_NAME}{school_id}")],
        [InlineKeyboardButton(text="✏️ Изменить краткое имя", callback_data=f"{CB_GA_ED_S_SHORT}{school_id}")],
        [InlineKeyboardButton(text="✏️ Изменить адрес", callback_data=f"{CB_GA_ED_S_ADDR}{school_id}")],
        [InlineKeyboardButton(text="🌍 Изменить таймзону", callback_data=f"{CB_GA_ED_S_TZ}{school_id}")],
        [InlineKeyboardButton(text="⬅ К списку УЗ", callback_data=CB_GA_EDIT_SCHOOLS)],
    ])

def student_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои задания",        callback_data=CB_STU_TASKS)],
        [InlineKeyboardButton(text="👨‍🏫 Мои преподаватели", callback_data=CB_STU_TEACHERS)],
        [InlineKeyboardButton(text="🏫 Мои группы",         callback_data=CB_STU_GROUPS)],
        [InlineKeyboardButton(text="📆 Расписание / напоминания", callback_data=CB_STU_SCHEDULE)],
        [InlineKeyboardButton(text="ℹ️ Информация",         callback_data=CB_STU_INFO)],
        [InlineKeyboardButton(text="🏠 Главное меню",       callback_data=CB_BACK)],
    ])

# список задач со входом в подробности (кнопки-строки + пагинация)
from callbacks import StudentCB, TaskCB  # если ты уже добавлял CB-классы для пагинации/деталей

def tasks_list_kb(tasks: list, page: int, has_next: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for row in tasks:
        kb.button(
            text=f"• {row['title']} ({row['class_name']})"[:64],
            callback_data=TaskCB(action="detail", task_id=row["task_id"], page=page).pack()
        )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=StudentCB(action="tasks", page=page-1).pack()))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️ Далее", callback_data=StudentCB(action="tasks", page=page+1).pack()))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data=CB_BACK))
    return kb.as_markup()

def task_detail_kb(back_page: int | None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if back_page is not None:
        kb.button(text="⬅️ К списку заданий", callback_data=StudentCB(action="tasks", page=back_page).pack())
    kb.button(text="🏠 Главное меню", callback_data=CB_BACK)
    kb.adjust(1)
    return kb.as_markup()
