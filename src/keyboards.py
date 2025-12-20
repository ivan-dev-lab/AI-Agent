# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Tuple
from aiogram.utils.keyboard import InlineKeyboardBuilder
from callbacks import StudentCB, TaskCB


from callbacks import (
    CB_BACK,
    CB_SETTINGS,
    CB_ADD_TASK,
    CB_LIST_TASKS,
    CB_ADD_CLASS,
    CB_ADD_STUDENT,
    CB_ENROLL,
    CB_REGISTER,
    CB_GEN,
    CB_T_ASSIGN_STUDENT,
    CB_T_EDIT_STUDENTS,
    CB_T_CREATE_GROUP,
    CB_T_EDIT_GROUP,
    CB_T_ADD_TASK,
    CB_T_LIST_TASKS,
    CB_STU_TASKS,
    CB_STU_TEACHERS,
    CB_STU_GROUPS,
    CB_STU_SCHEDULE,
    CB_STU_INFO,
    CB_LA_SEC_CORE,
    CB_LA_SEC_INFO,
    CB_LA_ASSIGN_TEACHER,
    CB_LA_ASSIGN_STUDENT,
    CB_LA_EDIT_TEACHERS,
    CB_LA_EDIT_STUDENTS,
    CB_LA_LIST_TEACHERS,
    CB_LA_LIST_STUDENTS,
    CB_LA_LIST_LOCAL_ADMINS,
    CB_LA_CREATE_SCHOOL,
    CB_LA_BACK_TO_CORE,
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

def teacher_main_kb() -> InlineKeyboardMarkup:
    """
    Главное меню для роли Учитель (teacher).
    Пункты соответствуют скриншоту: назначить ученика, редактирование учеников,
    создать группу, редактировать группу (добавить/удалить), добавить задание, список заданий.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🎓 Добавить ученика", callback_data=CB_T_ASSIGN_STUDENT)],
        [InlineKeyboardButton(text="✏️ Редактировать учеников", callback_data=CB_T_EDIT_STUDENTS)],
        [InlineKeyboardButton(text="📁 Создать группу", callback_data=CB_T_CREATE_GROUP)],
        [InlineKeyboardButton(text="⚙️ Редактировать группу (добавить/удалить)", callback_data=CB_T_EDIT_GROUP)],
        [InlineKeyboardButton(text="➕ Добавить задание", callback_data=CB_T_ADD_TASK)],
        [InlineKeyboardButton(text="📋 Список заданий", callback_data=CB_T_LIST_TASKS)]
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



def la_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧱 Основные", callback_data=CB_LA_SEC_CORE)],
        [InlineKeyboardButton(text="📚 Информационные", callback_data=CB_LA_SEC_INFO)]
    ])


def la_core_kb() -> InlineKeyboardMarkup:
    rows = [
        ('Create school and self-assign', CB_LA_CREATE_SCHOOL),
        ('Assign teacher', CB_LA_ASSIGN_TEACHER),
        ('Assign student', CB_LA_ASSIGN_STUDENT),
        ('Edit teachers', CB_LA_EDIT_TEACHERS),
        ('Edit students', CB_LA_EDIT_STUDENTS),
        ('Back to sections', CB_LA_BACK_TO_CORE),
    ]
    return single_col_kb(rows)


def la_info_kb() -> InlineKeyboardMarkup:
    rows = [
        ("📋 Список учителей", CB_LA_LIST_TEACHERS),
        ("📋 Список учеников", CB_LA_LIST_STUDENTS),
        ("📋 Список локальных админов", CB_LA_LIST_LOCAL_ADMINS),
        ("⬅ Назад к разделам", CB_LA_BACK_TO_CORE)
    ]
    return single_col_kb(rows)


def student_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои задания",        callback_data=CB_STU_TASKS)],
        [InlineKeyboardButton(text="👨‍🏫 Мои преподаватели", callback_data=CB_STU_TEACHERS)],
        [InlineKeyboardButton(text="🏫 Мои группы",         callback_data=CB_STU_GROUPS)],
        [InlineKeyboardButton(text="📆 Расписание / напоминания", callback_data=CB_STU_SCHEDULE)],
        [InlineKeyboardButton(text="ℹ️ Информация",         callback_data=CB_STU_INFO)],
    ])

# список задач со входом в подробности (кнопки-строки + пагинация)

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

def task_detail_kb(back_page: int | None, task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if back_page is not None:
        kb.button(text="⬅️ К списку заданий", callback_data=StudentCB(action="tasks", page=back_page).pack())
    # Добавляем две новые кнопки — нейросеть и учитель
    kb.row(
        InlineKeyboardButton(
            text="🤖 Спросить у нейросети",
            callback_data=TaskCB(action="ask_ai", task_id=task_id, page=back_page).pack()
        ),
        InlineKeyboardButton(
            text="✉️ Спросить у учителя",
            callback_data=TaskCB(action="ask_teacher", task_id=task_id, page=back_page).pack()
        )
    )
    kb.button(text="🏠 Главное меню", callback_data=CB_BACK)
    kb.adjust(1)
    return kb.as_markup()
