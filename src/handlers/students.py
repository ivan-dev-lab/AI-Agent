from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from utils import ensure_role, fmt_dt_local
from utils import ensure_role, fmt_dt_local
from callbacks import (
    CB_STU_MENU, CB_STU_TASKS, CB_STU_TEACHERS, CB_STU_GROUPS, CB_STU_SCHEDULE, CB_STU_INFO, CB_BACK
    CB_STU_MENU, CB_STU_TASKS, CB_STU_TEACHERS, CB_STU_GROUPS, CB_STU_SCHEDULE, CB_STU_INFO, CB_BACK
)
from keyboards import student_menu_kb, tasks_list_kb
from db import (
    list_tasks_for_student, list_classes_for_student, list_teachers_for_student, upcoming_tasks_for_student
)
from zoneinfo import ZoneInfo
from config import DEFAULT_TZ
from keyboards import student_menu_kb, tasks_list_kb
from db import (
    list_tasks_for_student, list_classes_for_student, list_teachers_for_student, upcoming_tasks_for_student
)
from zoneinfo import ZoneInfo
from config import DEFAULT_TZ

router = Router()
PAGE_SIZE = 8


@router.message(Command("student"))
async def student_menu_cmd(msg: Message):
    if not await ensure_role(msg.from_user.id, "student", msg):
        return
    await msg.answer("🎓 Меню ученика", reply_markup=student_menu_kb())


@router.callback_query(F.data == CB_STU_MENU)
async def student_menu_cb(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return
    await cq.message.edit_text("🎓 Меню ученика", reply_markup=student_menu_kb())
    await cq.answer()


# --- Мои задания (список + вход в подробности через кнопки-строки)
from callbacks import StudentCB  # для пагинации и возврата


@router.callback_query(F.data == CB_STU_TASKS)
async def student_tasks_entry(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return
    page = 0
    tasks, has_next = await list_tasks_for_student(cq.from_user.id, limit=PAGE_SIZE, offset=0)
    text = (
        "📋 Мои задания\n\nВыберите задание, чтобы открыть подробности."
        if tasks else
        "📋 Мои задания\n\nПока заданий нет."
    )
    await cq.message.edit_text(text, reply_markup=tasks_list_kb(tasks, page, has_next))
    await cq.answer()


# --- Мои преподаватели
@router.callback_query(F.data == CB_STU_TEACHERS)
async def student_teachers(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return

    rows = await list_teachers_for_student(cq.from_user.id)
    if not rows:
        text = "👨‍🏫 Мои преподаватели\n\nПока список пуст."
    else:
        text = "👨‍🏫 Мои преподаватели:\n\n" + "\n".join([f"• {r['name']}" for r in rows])

    from keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню ученика", callback_data=CB_STU_MENU)],
    ])

    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()


# --- Мои группы
@router.callback_query(F.data == CB_STU_GROUPS)
async def student_groups(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return

    rows = await list_classes_for_student(cq.from_user.id)
    if not rows:
        text = "🏫 Мои группы\n\nВы пока не записаны ни в один класс."
    else:
        text = "🏫 Мои группы:\n\n" + "\n".join([f"• {r['name']}" for r in rows])

    from keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню ученика", callback_data=CB_STU_MENU)],
    ])

    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()


# --- Расписание / напоминания (ближайшие дедлайны)
@router.callback_query(F.data == CB_STU_SCHEDULE)
async def student_schedule(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return

    rows = await upcoming_tasks_for_student(cq.from_user.id, limit=10)
    if not rows:
        text = "📆 Расписание / напоминания\n\nБлижайших дедлайнов нет."
    else:
        tz = ZoneInfo(DEFAULT_TZ)
        lines = []
        from datetime import datetime
        for r in rows:
            due = datetime.fromisoformat(r["due_utc"]).astimezone(tz).strftime("%Y-%m-%d %H:%M")
            lines.append(f"• {r['title']} — {r['class_name']} — {due} {tz.key}")
        text = "📆 Расписание / напоминания\n\n" + "\n".join(lines)

    from keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню ученика", callback_data=CB_STU_MENU)],
    ])

    # защита от "message is not modified": если текст тот же самый, не дергаем edit_text
    current_text = cq.message.text or cq.message.html_text
    if current_text == text:
        await cq.answer()
        return

    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()


# --- Информация
@router.callback_query(F.data == CB_STU_INFO)
async def student_info(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return

    text = (
        "ℹ️ <b>Информация</b>\n\n"
        "• Используйте раздел «📋 Мои задания», чтобы открыть список и подробности.\n"
        "• «📆 Расписание» показывает ближайшие дедлайны.\n"
        "• По вопросам доступа — свяжитесь с администратором вашей школы."
    )
    from keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню ученика", callback_data=CB_STU_MENU)],
    ])

    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()
