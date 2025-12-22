import logging
import os
import asyncio
import json
from datetime import datetime

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from zoneinfo import ZoneInfo

from utils import ensure_role, fmt_dt_local
from callbacks import (
    CB_STU_MENU, CB_STU_TASKS, CB_STU_TEACHERS, CB_STU_GROUPS, CB_STU_SCHEDULE, CB_STU_INFO, CB_BACK, StudentCB, TaskCB
)
from keyboards import student_menu_kb, tasks_list_kb, task_detail_kb
from db import (
    list_tasks_for_student, list_classes_for_student,
    list_teachers_for_student, upcoming_tasks_for_student, get_task_with_class
)
from config import DEFAULT_TZ, DEFAULT_TZINFO, GENAPI_TOKEN
from services.genapi_client import call_genapi, DEFAULT_ENDPOINT as GENAPI_ENDPOINT, _extract_content

router = Router()
logger = logging.getLogger(__name__)
PAGE_SIZE = 8


def _format_task_due(due_iso: str | None, class_tz: str | None) -> str:
    """Форматирует дедлайн задачи в часовом поясе класса."""
    try:
        tz = ZoneInfo(class_tz or DEFAULT_TZ)
    except Exception:
        tz = DEFAULT_TZINFO
    try:
        dt = datetime.fromisoformat(due_iso) if due_iso else None
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=DEFAULT_TZINFO)
        return fmt_dt_local(dt, tz) if dt else "—"
    except Exception:
        return due_iso or "—"


def _normalize_due_dt(due_iso: str | None) -> datetime | None:
    if not due_iso:
        return None
    try:
        due_dt = datetime.fromisoformat(due_iso)
    except Exception:
        return None
    if due_dt.tzinfo is None:
        due_dt = due_dt.replace(tzinfo=DEFAULT_TZINFO)
    return due_dt.astimezone(DEFAULT_TZINFO)



from datetime import datetime

def _tasks_list_text(tasks: list, page: int) -> str:
    if not tasks:
        return "📋 <b>Мои задания</b>\n\nПока заданий нет."

    start_idx = page * PAGE_SIZE + 1
    now = datetime.now(DEFAULT_TZINFO)
    overdue_lines = []
    upcoming_lines = []
    for idx, row in enumerate(tasks, start_idx):
        row_map = dict(row)
        title = row_map.get("title") or "Без названия"
        due_str = _format_task_due(row_map.get("due_utc"), row_map.get("class_tz"))
        due_dt = _normalize_due_dt(row_map.get("due_utc"))
        line = f"<b>№ {idx}</b>: {title}\nДедлайн: {due_str}"
        if due_dt and due_dt < now:
            overdue_lines.append(line)
        else:
            upcoming_lines.append(line)

    sections = []
    if overdue_lines:
        sections.append(
            "<b>Просроченные задания</b>:\n" + "\n\n".join(overdue_lines)
        )
    if upcoming_lines:
        sections.append(
            "<b>Актуальные задания</b>:\n" + "\n\n".join(upcoming_lines)
        )

    return "<b>📋 Мои задания</b>\n\n" + "\n\n".join(sections)




GENAPI_FALLBACK_TOKEN = "sk-v6FKLfILfda7HreS8zOPZ5Rcp8hcJBeNJnX1QZoiS7H2H5QOta9j9FXFS1nM"


def _get_genapi_token() -> str:
    """Берём токен из config/env, при отсутствии — используем выданный пользователем fallback."""
    return (GENAPI_TOKEN or os.getenv("GENAPI_TOKEN") or GENAPI_FALLBACK_TOKEN).strip()


def _format_task_context(task_row) -> str:
    """Формирует контекст задания для AI.

    В БД мы часто работаем с aiosqlite.Row (sqlite3.Row), у которого нет метода .get().
    Поэтому нормализуем к dict.
    """
    if task_row is None:
        task_row = {}
    elif not isinstance(task_row, dict):
        try:
            task_row = dict(task_row)
        except Exception:
            task_row = {}

    title = task_row.get("title") or "Без названия"
    desc = task_row.get("description") or "Описание отсутствует"
    class_name = task_row.get("class_name") or "Без группы"
    due_utc = task_row.get("due_utc")
    try:
        tz = ZoneInfo(DEFAULT_TZ)
        due_dt = datetime.fromisoformat(due_utc)
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=DEFAULT_TZINFO)
        due_str = fmt_dt_local(due_dt, tz)
    except Exception:
        due_str = due_utc or "Без даты"

    return (
        f"Задание: {title}\n"
        f"Описание: {desc}\n"
        f"Класс/группа: {class_name}\n"
        f"Дедлайн: {due_str}"
    )


def _build_ai_messages(task_ctx: str, user_question: str) -> list[dict]:
    system_prompt = (
        "Ты дружелюбный учебный ассистент. Помогаешь университетскику разобраться с домашним заданием, "
        "объясняешь шаги и даёшь короткий, понятный ответ. Если чего-то не хватает в условии, "
        "подскажи, что уточнить. Не придумывай факты."
    )
    user_prompt = (
        f"Контекст задания:\n{task_ctx}\n\n"
        f"Вопрос студента:\n{user_question}\n\n"
        "Дай чёткий, пошаговый ответ. Если нужно — предложи простой пример или план решения."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def _typing(message: Message):
    """Отправляет статус 'печатает' пока задача активна."""
    try:
        while True:
            await message.bot.send_chat_action(message.chat.id, "typing")
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        return


def _normalize_ai_answer(raw: str) -> str:
    """
    Если в ответе осталось JSON-представление, попробуем извлечь текст.
    """
    if not raw:
        return raw
    try:
        parsed = json.loads(raw)
    except Exception:
        return raw
    extracted = _extract_content(parsed)
    return extracted if extracted else raw



class AskAIState(StatesGroup):
    waiting_for_query = State()
    selected_task_id = State()


@router.message(Command("student"))
async def student_menu_cmd(msg: Message):
    if not await ensure_role(msg.from_user.id, "student", msg):
        return
    await msg.answer("🎓 Меню студента", reply_markup=student_menu_kb())


@router.callback_query(F.data == CB_STU_MENU)
async def student_menu_cb(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return
    await cq.message.edit_text("🎓 Меню студента", reply_markup=student_menu_kb())
    await cq.answer()



from callbacks import StudentCB



@router.callback_query(F.data == CB_STU_TASKS)
async def student_tasks_entry(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return
    page = 0
    tasks, has_next = await list_tasks_for_student(cq.from_user.id, limit=PAGE_SIZE, offset=0)
    start_idx = page * PAGE_SIZE + 1
    text = _tasks_list_text(tasks, page)
    await cq.message.edit_text(text, reply_markup=tasks_list_kb(tasks, page, has_next, start_idx))
    await cq.answer()


@router.callback_query(StudentCB.filter(F.action == "tasks"))
async def student_tasks_paged(cq: CallbackQuery, callback_data: StudentCB):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return
    page = callback_data.page or 0
    offset = page * PAGE_SIZE
    tasks, has_next = await list_tasks_for_student(cq.from_user.id, limit=PAGE_SIZE, offset=offset)
    start_idx = page * PAGE_SIZE + 1
    text = _tasks_list_text(tasks, page)
    await cq.message.edit_text(text, reply_markup=tasks_list_kb(tasks, page, has_next, start_idx))
    await cq.answer()

@router.callback_query(TaskCB.filter(F.action == "detail"))
async def open_task(callback: CallbackQuery, callback_data: TaskCB):
    if not await ensure_role(callback.from_user.id, "student", callback):
        return

    task = await get_task_with_class(callback_data.task_id)
    if not task:
        await callback.answer("Задание не найдено", show_alert=True)
        return

    text = f"📘 *{task['title']}*\n\n{task['description'] or 'Без описания'}"
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=task_detail_kb(callback_data.page, callback_data.task_id)
    )
    await callback.answer()


@router.callback_query(TaskCB.filter(F.action == "ask_ai"))
async def ask_ai(callback: CallbackQuery, callback_data: TaskCB, state: FSMContext):
    if not await ensure_role(callback.from_user.id, "student", callback):
        return

    task_id = callback_data.task_id
    await state.update_data(selected_task_id=task_id, back_page=callback_data.page)

    await callback.message.answer("✍️ Введи свой вопрос для нейросети:")
    await state.set_state(AskAIState.waiting_for_query)
    await callback.answer()


@router.message(AskAIState.waiting_for_query)
async def process_ai_query(message: Message, state: FSMContext):
    user_data = await state.get_data()
    task_id = user_data.get("selected_task_id")

    query_text = (message.text or "").strip()
    if not query_text:
        await message.answer("Пожалуйста, введите корректный запрос.")
        return

    task = await get_task_with_class(task_id) if task_id else None
    if not task:
        await message.answer(
            "Не удалось найти задание. Откройте задание заново и повторите вопрос."
        )
        await state.clear()
        return

    status_msg = await message.answer("⏳ Нейросеть обрабатывает ваш запрос...")
    typing_task = asyncio.create_task(_typing(message))

    task_context = _format_task_context(dict(task))
    messages = _build_ai_messages(task_context, query_text)

    progress_step = {"i": 0}

    async def on_progress(data: dict):
        progress_step["i"] += 1
        dots = "." * (progress_step["i"] % 3 + 1)
        status = data.get("status") or "processing"
        try:
            await status_msg.edit_text(f"⏳ Нейросеть думает{dots}\nСтатус: {status}")
        except Exception:
            pass

    try:
        ai_answer = await call_genapi(
            messages,
            api_key=_get_genapi_token(),
            endpoint=GENAPI_ENDPOINT,
            poll=True,
            poll_interval=1,
            poll_timeout=60,
            on_progress=on_progress,
        )
    except Exception as e:
        logger.exception("GenAPI error")
        await status_msg.edit_text(
            "Не удалось получить ответ от нейросети. Попробуйте ещё раз чуть позже."
            f"\nОшибка: {e}"
        )
        await state.clear()
        typing_task.cancel()
        return

    typing_task.cancel()
    ai_answer = _normalize_ai_answer(ai_answer)
    answer_body = ai_answer if ai_answer else "Ответ пустой. Попробуйте задать вопрос чуть иначе."
    final_text = f"🤖 Ответ нейросети по заданию\n\n{answer_body}"
    try:
        await status_msg.edit_text(final_text, parse_mode="Markdown")
    except Exception:
        await status_msg.edit_text(final_text)

    await state.clear()

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
        [InlineKeyboardButton(text="🔙 В меню студента", callback_data=CB_STU_MENU)],
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Меню студента", callback_data=CB_STU_MENU)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CB_BACK)],
    ])
    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()




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
        [InlineKeyboardButton(text="🔙 В меню студента", callback_data=CB_STU_MENU)],
    ])

    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()



@router.callback_query(F.data == CB_STU_SCHEDULE)
async def student_schedule(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return

    rows = await upcoming_tasks_for_student(cq.from_user.id, limit=10)
    if not rows:
        text = "📆 Расписание \n\nБлижайших дедлайнов нет."
    else:
        tz = ZoneInfo(DEFAULT_TZ)
        lines = []
        from datetime import datetime
        for r in rows:
            due_dt = datetime.fromisoformat(r["due_utc"])
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=DEFAULT_TZINFO)
            due = fmt_dt_local(due_dt, tz)
            lines.append(f"• {r['title']} — {r['class_name']} — {due}")
        text = "📆 Расписание \n\n" + "\n".join(lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню студента", callback_data=CB_STU_MENU)],
    ])


    current_text = cq.message.text or cq.message.html_text
    if current_text == text:
        await cq.answer()
        return

    await cq.message.edit_text(text, reply_markup=kb)
    await cq.answer()



@router.callback_query(F.data == CB_STU_INFO)
async def student_info(cq: CallbackQuery):
    if not await ensure_role(cq.from_user.id, "student", cq):
        return

    text = (
        "ℹ️ <b>Информация</b>\n\n"
        "• Используйте раздел «📋 Мои задания», чтобы открыть список и подробности.\n"
        "• «📆 Расписание» показывает ближайшие дедлайны.\n"
        "• По вопросам доступа — свяжитесь с администратором вашего университета."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В меню студента", callback_data=CB_STU_MENU)],
    ])

    await cq.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cq.answer()
