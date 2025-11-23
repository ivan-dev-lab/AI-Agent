import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from utils import ensure_role, fmt_dt_local
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from zoneinfo import ZoneInfo

from callbacks import (
    CB_STU_MENU, CB_STU_TASKS, CB_STU_TEACHERS, CB_STU_GROUPS,
    CB_STU_SCHEDULE, CB_STU_INFO, CB_BACK, StudentCB
)
from keyboards import student_menu_kb, tasks_list_kb
from db import (
    list_tasks_for_student, list_classes_for_student,
    list_teachers_for_student, upcoming_tasks_for_student
)
# from src.utils import send_to_neural_api
from config import DEFAULT_TZ

router = Router()
logger = logging.getLogger(__name__)
PAGE_SIZE = 8

# Состояния для нейросети
class AskAIState(StatesGroup):
    waiting_for_query = State()
    selected_task_id = State()

# Главное меню ученика
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

# Мои задания с пагинацией
@router.callback_query(F.data == CB_STU_TASKS)
async def student_tasks_entry(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return
    page = 0
    tasks, has_next = await list_tasks_for_student(cq.from_user.id, limit=PAGE_SIZE, offset=0)
    text = "📋 Мои задания\n\nВыберите задание, чтобы открыть подробности." if tasks else "📋 Мои задания\n\nПока заданий нет."
    await cq.message.edit_text(text, reply_markup=tasks_list_kb(tasks, page, has_next))
    await cq.answer()

# Открытие конкретного задания
@router.callback_query(F.data.startswith("open_task_"))
async def open_task(callback: CallbackQuery, state: FSMContext):
    if not await ensure_role(callback.from_user.id, "student", callback):
        return

    task_id = int(callback.data.split("_")[-1])

    # Получаем список заданий и находим нужное
    tasks, _ = await list_tasks_for_student(callback.from_user.id, limit=100, offset=0)
    task = next((t for t in tasks if t['id'] == task_id), None)

    if not task:
        await callback.message.answer("Задание не найдено.")
        return

    # Клавиатура с двумя новыми кнопками
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑‍🏫 Спросить у учителя", callback_data=f"ask_teacher_{task_id}")],
        [InlineKeyboardButton(text="🤖 Спросить у нейросети", callback_data=f"ask_ai_{task_id}")],
        [InlineKeyboardButton(text="🔙 Назад к заданиям", callback_data=CB_STU_TASKS)]
    ])

    await callback.message.edit_text(
        f"📘 *{task['title']}*\n\n{task['description']}",
        parse_mode="Markdown",
        reply_markup=kb
    )
    await callback.answer()

# Обработчик кнопки «Спросить у учителя» (заглушка)
@router.callback_query(F.data.startswith("ask_teacher_"))
async def ask_teacher(callback: CallbackQuery):
    if not await ensure_role(callback.from_user.id, "student", callback):
        return

    task_id = int(callback.data.split("_")[-1])
    await callback.message.answer(
        f"🧑‍🏫 Отправляю вопрос учителю по заданию #{task_id}...\n\n"
        "Ожидайте ответа — учитель скоро свяжется с вами."
    )
    await callback.answer()

# Начало диалога с нейросетью
@router.callback_query(F.data.startswith("ask_ai_"))
async def ask_ai(callback: CallbackQuery, state: FSMContext):
    if not await ensure_role(callback.from_user.id, "student", callback):
        return

    task_id = int(callback.data.split("_")[-1])
    await state.update_data(selected_task_id=task_id)

    await callback.message.answer("✍️ Введи свой вопрос для нейросети:")
    await state.set_state(AskAIState.waiting_for_query)
    await callback.answer()

# Обработка ввода пользователя и ответ нейросети (заглушка)
@router.message(AskAIState.waiting_for_query)
async def process_ai_query(message: Message, state: FSMContext):
    user_data = await state.get_data()
    task_id = user_data.get("selected_task_id")

    query_text = message.text.strip()
    if not query_text:
        await message.answer("Пожалуйста, введите корректный запрос.")
        return

    await message.answer("⏳ Нейросеть обрабатывает ваш запрос...")

    # Заглушка ответа нейросети
    mock_response = (
        f"Я — тестовая версия нейросети.\n\n"
        f"Вы задали вопрос: *{query_text}*\n\n"
        f"По заданию #{task_id} я могу предположить следующее:\n\n"
        "Это пример ответа от нейросети. В реальной версии сюда придёт ответ от API."
    )

    await message.answer(mock_response, parse_mode="Markdown")
    await state.clear()

# Преподаватели
@router.callback_query(F.data == CB_STU_TEACHERS)
async def student_teachers(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return
    rows = await list_teachers_for_student(cq.from_user.id)
    if not rows:
        text = "👨‍🏫 Мои преподаватели\n\nПока список пуст."
        kb = student_menu_kb()
    else:
        text = "👨‍🏫 Мои преподаватели:\n\n" + "\n".join([f"• {r['name']}" for r in rows])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Меню ученика", callback_data=CB_STU_MENU)],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CB_BACK)],
        ])
    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()

# Группы
@router.callback_query(F.data == CB_STU_GROUPS)
async def student_groups(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return
    rows = await list_classes_for_student(cq.from_user.id)
    if not rows:
        text = "🏫 Мои группы\n\nВы пока не записаны ни в один класс."
    else:
        text = "🏫 Мои группы:\n\n" + "\n".join([f"• {r['name']}" for r in rows])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Меню ученика", callback_data=CB_STU_MENU)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CB_BACK)],
    ])
    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()

# Расписание / напоминания
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Меню ученика", callback_data=CB_STU_MENU)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CB_BACK)],
    ])
    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()

# Информация
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Меню ученика", callback_data=CB_STU_MENU)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CB_BACK)],
    ])
    await cq.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cq.answer()

