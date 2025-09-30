#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# TODO: сделать более красивое отображение заданий
# QUESTION: что за чат с учеником?
# TODO: сделать генерацию кода через нейронку
# TODO: настройки: как минимум таймзону выставить 

"""
Учебный Telegram-бот ИИ-агент для ESP32/MicroPython (aiogram 3)
Инлайн-меню, пошаговый ввод после кнопок, "Назад в главное меню".
Добавлено:
- После добавления ученика — сразу показ списка классов для зачисления (или «⏭ Пропустить»).
- "Записать ученика в класс" через список учеников и список классов (кнопки по одной в ряд, сортировка A–Я).
- Добавление задания: выбор класса через инлайн-кнопки (кнопки по одной в ряд, сортировка A–Я).
Стек: aiogram (async), LangChain + Ollama, SQLite (aiosqlite), APScheduler.
"""

import asyncio
import os
import re
from io import BytesIO
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Tuple

import dotenv
dotenv.load_dotenv(os.path.abspath('.env'))  # грузим .env до чтения os.getenv

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Message, BufferedInputFile, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

# # ---- LangChain (ChatOllama) ----
# from langchain_core.output_parsers import StrOutputParser
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_community.chat_models import ChatOllama

import pytz  # type: ignore

# ------------------ НАСТРОЙКИ ------------------
DEFAULT_MODEL = os.getenv("MODEL_NAME", "llama3:8b")
DB_PATH = os.getenv("DB_PATH", "agent.db")
DEFAULT_TZ = "UTC"  # по умолчанию UTC

REMINDER_OFFSETS = [
    ("T-24h", timedelta(hours=24)),
    ("T-3h", timedelta(hours=3)),
    ("T-15m", timedelta(minutes=15)),
    ("T0", timedelta(seconds=0)),
]

default_props = DefaultBotProperties(parse_mode='HTML')

# Глобальные ссылки (для APScheduler)
BOT: Bot | None = None
SCHEDULER: AsyncIOScheduler | None = None

# Выбранная модель на пользователя
USER_MODEL: Dict[int, str] = {}

# ---- Примитивный FSM (in-memory) ----
# USER_STATE[user_id] = {"mode": "...", "step": 0..n, "data": {...}, "chat_id": int}
USER_STATE: Dict[int, Dict[str, Any]] = {}

# ---------- PROMPTS ----------
SYSTEM_PROMPT = """\
You are an expert MicroPython tutor for ESP32-based educational robotics.
Your job: generate clean, safe, well-commented MicroPython code **first**, then include a short explanation at the end.
Constraints and style:
- Target platform: ESP32 with MicroPython standard modules only (machine, time, PWM etc.). Avoid uasyncio unless explicitly requested.
- No external libraries. No network unless explicitly requested.
- Always declare GPIO pins as named constants at the top (e.g., LED_PIN = 2).
- Use clear function structure, docstrings, and step-by-step comments for students.
- Add a short "Test Instructions" section as comments.
- If hardware is ambiguous, make safe assumptions and clearly list them in comments.
Return code enclosed in Markdown triple backticks with language 'python', then the explanation.
"""

# PROMPT = ChatPromptTemplate.from_messages([
#     ("system", SYSTEM_PROMPT),
#     ("human",
#      "Generate MicroPython code for ESP32 according to this description:\n"
#      "=== DESCRIPTION START ===\n{task_description}\n=== DESCRIPTION END ===\n\n"
#      "Make the code beginner-friendly with comments; then add a short explanation.")
# ])
# parser = StrOutputParser()


# def build_llm(model_name: str) -> ChatOllama:
#     return ChatOllama(model=model_name, temperature=0.2)


# -------------------- БАЗА ДАННЫХ --------------------

async def fetchone(db, sql: str, params=()):
    cur = await db.execute(sql, params)
    row = await cur.fetchone()
    await cur.close()
    return row

async def fetchall(db, sql: str, params=()):
    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    await cur.close()
    return rows


async def ensure_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            owner_chat_id INTEGER NOT NULL,
            timezone TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            username TEXT,
            chat_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS enrollments (
            student_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            UNIQUE (student_id, class_id),
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_utc TEXT NOT NULL,
            created_utc TEXT NOT NULL,
            FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            run_at_utc TEXT NOT NULL,
            kind TEXT NOT NULL,
            UNIQUE(task_id, run_at_utc, kind),
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );
        """)
        await db.commit()


# -------------------- УТИЛИТЫ --------------------

def fmt_dt_local(dt_utc: datetime, tz: ZoneInfo) -> str:
    return dt_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M")

def extract_code_from_markdown(md: str) -> str:
    fence = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    m = fence.search(md)
    return m.group(1).strip() if m else md.strip()

def display_student(name: str, username: str | None) -> str:
    return f"{name} (@{username})" if username else f"{name} (—)"

# -------------------- КНОПКИ/МЕНЮ --------------------

# callback data (простые и префиксные)
CB_MAIN = "main"
CB_ADD_CLASS = "add_class"
CB_ADD_STUDENT = "add_student"
CB_ENROLL = "enroll"
CB_REGISTER = "register"
CB_ADD_TASK = "add_task"
CB_LIST_TASKS = "list_tasks"
CB_GEN = "gen"
CB_SETTINGS = "settings"
CB_BACK = "back_to_main"

# Префиксные коллбэки для выбора
CB_ENROLL_PICK_STU = "enroll_pick_stu:"       # +<student_id>
CB_ENROLL_PICK_CLS = "enroll_pick_cls:"       # +<student_id>:<class_id>

# После создания студента: предложить зачислить в класс/пропустить
CB_STU_AFTER_ADD_ENROLL = "stu_after_add_enroll:"  # +<student_id>
CB_STU_AFTER_ADD_SKIP = "stu_after_add_skip"

# Добавление задания: выбор класса
CB_ADD_TASK_PICK_CLASS = "addtask_pick_cls:"  # +<class_id>

def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад в главное меню", callback_data=CB_BACK)]
    ])

def single_col_kb(rows: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    """rows: [(text, callback_data)] => клавиатура по одной кнопке в ряд."""
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

async def show_main_menu(target):
    text = (
        "🏁 <b>Главное меню</b>\n\n"
        "Выберите действие. Ввод данных происходит <i>после</i> нажатия кнопки.\n"
        "Таймзона по умолчанию: <b>UTC</b>.\n"
    )
    if isinstance(target, Message):
        await target.answer(text, reply_markup=main_menu_kb())
    else:
        await target.message.edit_text(text, reply_markup=main_menu_kb())


# -------------------- APSCHEDULER --------------------
async def schedule_task_jobs(task_id: int):
    if SCHEDULER is None:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        task = await fetchone(db, "SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not task:
            return
        class_row = await fetchone(db, "SELECT * FROM classes WHERE id = ?", (task["class_id"],))
        if not class_row:
            return

        due_utc = datetime.fromisoformat(task["due_utc"]).replace(tzinfo=timezone.utc)
        for label, delta in REMINDER_OFFSETS:
            run_at_utc = due_utc - delta
            if run_at_utc <= datetime.now(timezone.utc):
                continue

            exists = await fetchone(
                db, "SELECT 1 FROM jobs WHERE task_id=? AND run_at_utc=? AND kind=?",
                (task_id, run_at_utc.isoformat(), label)
            )
            if exists:
                continue

            await db.execute(
                "INSERT OR IGNORE INTO jobs(task_id, run_at_utc, kind) VALUES (?, ?, ?)",
                (task_id, run_at_utc.isoformat(), label)
            )
            await db.commit()

            SCHEDULER.add_job(
                send_reminder_job,
                "date",
                run_date=run_at_utc,
                args=[task_id, label],
                id=f"task{task_id}_{label}_{int(run_at_utc.timestamp())}",
                misfire_grace_time=60
            )

async def rehydrate_jobs():
    if SCHEDULER is None:
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(db, "SELECT task_id, run_at_utc, kind FROM jobs WHERE run_at_utc > ?", (now_iso,))
    for r in rows:
        run_at_utc = datetime.fromisoformat(r["run_at_utc"]).replace(tzinfo=timezone.utc)
        SCHEDULER.add_job(
            send_reminder_job,
            "date",
            run_date=run_at_utc,
            args=[r["task_id"], r["kind"]],
            id=f"rehydrated_task{r['task_id']}_{r['kind']}_{int(run_at_utc.timestamp())}",
            misfire_grace_time=60
        )

async def send_reminder_job(task_id: int, when_label: str):
    if BOT is None:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        task = await fetchone(db, "SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not task:
            return
        class_row = await fetchone(db, "SELECT * FROM classes WHERE id = ?", (task["class_id"],))
        if not class_row:
            return

        tz = ZoneInfo(class_row["timezone"])
        due_utc = datetime.fromisoformat(task["due_utc"]).replace(tzinfo=timezone.utc)
        due_local_str = fmt_dt_local(due_utc, tz)
        teacher_chat = class_row["owner_chat_id"]

        students = await fetchall(
            db,
            """SELECT s.name, s.chat_id FROM students s
               JOIN enrollments e ON e.student_id = s.id
               WHERE e.class_id = ?""",
            (class_row["id"],)
        )

    header = (
        f"⏰ Напоминание ({when_label})\n"
        f"Класс: <b>{class_row['name']}</b>\n"
        f"Задание: <b>{task['title']}</b>\n"
        f"Дедлайн: <b>{due_local_str} {class_row['timezone']}</b>"
    )
    body = (
        f"\n\n<b>Описание:</b> {task['description'] or '—'}\n"
        "\nЧек-лист:\n"
        "• Проверьте, что код запускается на плате\n"
        "• Подписаны пины и параметры\n"
        "• Сдайте отчёт по формату"
    )

    missing = []
    for s in students:
        if s["chat_id"]:
            try:
                await BOT.send_message(chat_id=int(s["chat_id"]), text=header + body, parse_mode=ParseMode.HTML)
            except Exception:
                missing.append(s["name"])
        else:
            missing.append(s["name"])

    final_body = body
    if missing:
        final_body += "\n\n⚠️ Не зарегистрированы: " + ", ".join(missing)
    try:
        await BOT.send_message(chat_id=int(teacher_chat), text=header + final_body, parse_mode=ParseMode.HTML)
    except Exception:
        pass


# -------------------- РОУТЕР И ХЕНДЛЕРЫ --------------------
router = Router()

# ===== Главные команды =====
@router.message(Command("start"))
async def cmd_start(msg: Message):
    await show_main_menu(msg)

@router.message(Command("help"))
async def cmd_help(msg: Message):
    await show_main_menu(msg)

# ===== Обработка нажатий на инлайн-кнопки (общие) =====
@router.callback_query(F.data == CB_BACK)
async def cb_back(cq: CallbackQuery):
    USER_STATE.pop(cq.from_user.id, None)
    await show_main_menu(cq)

@router.callback_query(F.data == CB_SETTINGS)
async def cb_settings(cq: CallbackQuery):
    USER_STATE.pop(cq.from_user.id, None)
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        "• Таймзона: пока по умолчанию <b>UTC</b>.\n"
        "• В будущей версии тут можно будет выбрать свою IANA TZ.\n"
    )
    await cq.message.edit_text(text, reply_markup=back_kb())

# ===== Добавление класса =====
@router.callback_query(F.data == CB_ADD_CLASS)
async def cb_add_class(cq: CallbackQuery):
    USER_STATE[cq.from_user.id] = {"mode": "add_class", "step": 0, "data": {}, "chat_id": cq.message.chat.id}
    await cq.message.edit_text(
        "🏷 <b>Добавление класса</b>\n\n"
        "Шаг 1/1: отправьте <b>название класса</b>.\n\n"
        "Пример: <code>Робототехника-10А</code>\n", reply_markup=back_kb()
    )

# ===== Добавление ученика (сразу предлагаем зачислить) =====
@router.callback_query(F.data == CB_ADD_STUDENT)
async def cb_add_student(cq: CallbackQuery):
    USER_STATE[cq.from_user.id] = {"mode": "add_student", "step": 0, "data": {}, "chat_id": cq.message.chat.id}
    await cq.message.edit_text(
        "👤 <b>Добавление ученика</b>\n\n"
        "Шаг 1/2: отправьте <b>имя ученика</b>.\n", reply_markup=back_kb()
    )

# ===== Зачисление ученика в класс (через списки кнопок) =====
@router.callback_query(F.data == CB_ENROLL)
async def cb_enroll(cq: CallbackQuery):
    # Список учеников (A–Я), 1 кнопка в ряд
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        students = await fetchall(db, "SELECT id, name, username FROM students ORDER BY name COLLATE NOCASE ASC")
    if not students:
        return await cq.message.edit_text("Пока нет учеников.", reply_markup=back_kb())
    rows = [(display_student(s["name"], s["username"]), f"{CB_ENROLL_PICK_STU}{s['id']}") for s in students]
    await cq.message.edit_text("🔗 <b>Выберите ученика</b>:", reply_markup=single_col_kb(rows))

@router.callback_query(F.data.startswith(CB_ENROLL_PICK_STU))
async def cb_enroll_pick_student(cq: CallbackQuery):
    # после выбора ученика — список классов
    try:
        student_id = int(cq.data.split(":")[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    USER_STATE[cq.from_user.id] = {"mode": "enroll_flow", "data": {"student_id": student_id}, "chat_id": cq.message.chat.id}

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        s = await fetchone(db, "SELECT name, username FROM students WHERE id=?", (student_id,))
        classes = await fetchall(db, "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC")
    if not s:
        return await cq.answer("Ученик не найден", show_alert=True)
    if not classes:
        return await cq.message.edit_text("Пока нет классов. Сначала создайте класс.", reply_markup=back_kb())

    student_title = display_student(s["name"], s["username"])
    rows = [(f"{c['name']}", f"{CB_ENROLL_PICK_CLS}{student_id}:{c['id']}") for c in classes]
    # добавим кнопку "⏭ Пропустить"
    rows.append(("⏭ Пропустить", CB_STU_AFTER_ADD_SKIP))
    await cq.message.edit_text(
        f"🔗 Ученик: <b>{student_title}</b>\n\nВыберите <b>класс</b>:",
        reply_markup=single_col_kb(rows)
    )

@router.callback_query(F.data.startswith(CB_ENROLL_PICK_CLS))
async def cb_enroll_pick_class(cq: CallbackQuery):
    # enroll студента в класс
    try:
        _, payload = cq.data.split(":", 1)
        student_id_str, class_id_str = payload.split(":")
        student_id = int(student_id_str)
        class_id = int(class_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        s = await fetchone(db, "SELECT name, username FROM students WHERE id=?", (student_id,))
        c = await fetchone(db, "SELECT name FROM classes WHERE id=?", (class_id,))
        if not s or not c:
            return await cq.answer("Ученик или класс не найден", show_alert=True)
        try:
            await db.execute("INSERT OR IGNORE INTO enrollments(student_id, class_id) VALUES(?, ?)", (student_id, class_id))
            await db.commit()
        except Exception as e:
            return await cq.message.edit_text(f"Ошибка: {e}", reply_markup=back_kb())

    USER_STATE.pop(cq.from_user.id, None)
    await cq.message.edit_text(
        f"✅ Привязка выполнена:\n"
        f"Ученик: <b>{display_student(s['name'], s['username'])}</b>\n"
        f"Класс: <b>{c['name']}</b>",
        reply_markup=back_kb()
    )

# ===== Привязка чата ученика =====
@router.callback_query(F.data == CB_REGISTER)
async def cb_register(cq: CallbackQuery):
    USER_STATE[cq.from_user.id] = {"mode": "register", "step": 0, "data": {}, "chat_id": cq.message.chat.id}
    await cq.message.edit_text(
        "💬 <b>Привязать чат ученика</b>\n\n"
        "Шаг 1/1: отправьте <b>имя ученика</b> для привязки к этому чату.\n", reply_markup=back_kb()
    )

# ===== Добавление задания (теперь выбор класса кнопками) =====
@router.callback_query(F.data == CB_ADD_TASK)
async def cb_add_task(cq: CallbackQuery):
    # показываем список классов
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        classes = await fetchall(db, "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC")
    if not classes:
        return await cq.message.edit_text(
            "📝 <b>Новое задание</b>\n\n"
            "Сначала создайте класс (меню → «🏷 Добавить класс»).",
            reply_markup=back_kb()
        )

    USER_STATE[cq.from_user.id] = {"mode": "add_task", "step": 0, "data": {}, "chat_id": cq.message.chat.id}
    rows = [(c["name"], f"{CB_ADD_TASK_PICK_CLASS}{c['id']}") for c in classes]
    await cq.message.edit_text(
        "📝 <b>Новое задание</b>\n\n"
        "Шаг 1/4: выберите <b>класс</b>:",
        reply_markup=single_col_kb(rows)
    )

@router.callback_query(F.data.startswith(CB_ADD_TASK_PICK_CLASS))
async def cb_add_task_pick_class(cq: CallbackQuery):
    # зафиксировать class_id и спросить заголовок
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        class_row = await fetchone(db, "SELECT id, name, timezone FROM classes WHERE id=?", (class_id,))
    if not class_row:
        return await cq.answer("Класс не найден", show_alert=True)

    USER_STATE[cq.from_user.id] = {
        "mode": "add_task",
        "step": 1,
        "data": {"class_id": class_row["id"], "class_name": class_row["name"]},
        "chat_id": cq.message.chat.id
    }
    await cq.message.edit_text(
        f"📝 <b>Новое задание</b>\n"
        f"Класс: <b>{class_row['name']}</b>\n\n"
        f"Шаг 2/4: отправьте <b>название задания</b>.",
        reply_markup=back_kb()
    )

# ===== Список заданий =====
@router.callback_query(F.data == CB_LIST_TASKS)
async def cb_list_tasks(cq: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(
            db,
            """SELECT t.*, c.name AS class_name, c.timezone
               FROM tasks t JOIN classes c ON c.id=t.class_id
               ORDER BY due_utc ASC"""
        )
    if not rows:
        text = "📋 Заданий пока нет."
    else:
        lines = ["<b>📋 Список заданий</b>"]
        for r in rows:
            tz = ZoneInfo(r["timezone"])
            due_local_str = fmt_dt_local(datetime.fromisoformat(r["due_utc"]).replace(tzinfo=timezone.utc), tz)
            lines.append(f"#{r['id']} • {r['class_name']} • <b>{r['title']}</b> — {due_local_str} {tz.key}")
        text = "\n".join(lines)
    await cq.message.edit_text(text, reply_markup=back_kb())

# ===== Генерация кода =====
@router.callback_query(F.data == CB_GEN)
async def cb_gen(cq: CallbackQuery):
    USER_STATE[cq.from_user.id] = {"mode": "gen", "step": 0, "data": {}, "chat_id": cq.message.chat.id}
    await cq.message.edit_text(
        "🤖 <b>Генерация MicroPython</b>\n\n"
        "Шаг 1/1: опишите задание текстом. Пример:\n"
        "<i>Кнопка на GPIO12 включает LED на GPIO2 на 3 секунды, PWM 50%</i>\n",
        reply_markup=back_kb()
    )

# ===== Обработка текстовых ответов (FSM) =====
@router.message(F.text)
async def on_text(msg: Message):
    state = USER_STATE.get(msg.from_user.id)
    if not state:
        return await show_main_menu(msg)

    mode = state["mode"]
    step = state.get("step", 0)
    data = state.setdefault("data", {})

    # ---------- ADD CLASS ----------
    if mode == "add_class":
        name = msg.text.strip()
        tz_key = DEFAULT_TZ
        async with aiosqlite.connect(DB_PATH) as db:
            try:
                await db.execute(
                    "INSERT INTO classes(name, owner_chat_id, timezone) VALUES (?, ?, ?)",
                    (name, msg.chat.id, tz_key)
                )
                await db.commit()
            except Exception as e:
                await msg.answer(f"Ошибка создания класса: {e}", reply_markup=back_kb())
                return
        USER_STATE.pop(msg.from_user.id, None)
        await msg.answer(f"✅ Класс создан: <b>{name}</b> (TZ={tz_key})", reply_markup=back_kb())
        return

    # ---------- ADD STUDENT (сразу предлагаем зачисление) ----------
    if mode == "add_student":
        if step == 0:
            data["name"] = msg.text.strip()
            state["step"] = 1
            return await msg.answer("Шаг 2/2: отправьте @username (или оставьте пустым — напишите «-»).",
                                    reply_markup=back_kb())
        elif step == 1:
            username = msg.text.strip()
            if username == "-":
                username = None
            else:
                username = username.lstrip("@") if username else None
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row  # dict-like строки
                try:
                    await db.execute(
                        "INSERT INTO students(name, username) VALUES (?, ?) "
                        "ON CONFLICT(name) DO UPDATE SET username=excluded.username",
                        (data["name"], username)
                    )
                    await db.commit()
                    row = await fetchone(db, "SELECT id, name, username FROM students WHERE name=?", (data["name"],))
                    student_id = row["id"]
                except Exception as e:
                    await msg.answer(f"Ошибка: {e}", reply_markup=back_kb())
                    return

                classes = await fetchall(db, "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC")

            if not classes:
                USER_STATE.pop(msg.from_user.id, None)
                return await msg.answer(
                    f"✅ Ученик добавлен/обновлён: <b>{data['name']}</b> (@{username or '—'})\n\n"
                    f"Пока нет классов — создайте класс и запишите ученика позже.",
                    reply_markup=back_kb()
                )

            USER_STATE.pop(msg.from_user.id, None)
            rows = [(c["name"], f"{CB_ENROLL_PICK_CLS}{student_id}:{c['id']}") for c in classes]
            rows.append(("⏭ Пропустить", CB_STU_AFTER_ADD_SKIP))
            return await msg.answer(
                f"✅ Ученик добавлен/обновлён: <b>{data['name']}</b> (@{username or '—'})\n\n"
                f"Сразу записать в класс?",
                reply_markup=single_col_kb(rows)
            )

    # ---------- REGISTER ----------
    if mode == "register":
        student_name = msg.text.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("UPDATE students SET chat_id=? WHERE name=?", (msg.chat.id, student_name))
            await db.commit()
            if cur.rowcount == 0:
                return await msg.answer("Ученик не найден. Сначала добавьте его.", reply_markup=back_kb())
        USER_STATE.pop(msg.from_user.id, None)
        await msg.answer(f"✅ Чат привязан к ученику: <b>{student_name}</b>", reply_markup=back_kb())
        return

    # ---------- ADD TASK (теперь шаги 1..3, класс уже выбран кнопкой) ----------
    if mode == "add_task":
        # step 1: title
        if step == 1:
            data["title"] = msg.text.strip()
            state["step"] = 2
            return await msg.answer(
                "Шаг 3/4: отправьте <b>дедлайн в UTC</b> в формате <code>YYYY-MM-DD HH:MM</code>.\n"
                "Пример: <code>2025-09-25 18:00</code>",
                reply_markup=back_kb()
            )
        # step 2: deadline
        elif step == 2:
            due_str = msg.text.strip()
            try:
                due_utc = datetime.strptime(due_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            except Exception:
                return await msg.answer("❌ Некорректная дата. Нужен формат: YYYY-MM-DD HH:MM (UTC).",
                                        reply_markup=back_kb())
            data["due_utc"] = due_utc
            state["step"] = 3
            return await msg.answer("Шаг 4/4: отправьте <b>описание</b> (или «-»).", reply_markup=back_kb())
        # step 3: description -> save
        elif step == 3:
            description = msg.text.strip()
            if description == "-":
                description = ""
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                class_row = await fetchone(db, "SELECT * FROM classes WHERE id=?", (data["class_id"],))
                if not class_row:
                    return await msg.answer("Класс не найден (возможно, был удалён).", reply_markup=back_kb())
                tz = ZoneInfo(class_row["timezone"])
                await db.execute(
                    "INSERT INTO tasks(class_id, title, description, due_utc, created_utc) VALUES(?, ?, ?, ?, ?)",
                    (
                        class_row["id"], data["title"], description,
                        data["due_utc"].astimezone(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat()
                    )
                )
                await db.commit()
                row = await fetchone(db, "SELECT last_insert_rowid() AS id")
                task_id = row["id"]
            await schedule_task_jobs(task_id)
            due_local_str = fmt_dt_local(data["due_utc"], tz)
            USER_STATE.pop(msg.from_user.id, None)
            return await msg.answer(
                f"✅ Задание создано: <b>{data['title']}</b>\n"
                f"Класс: <b>{class_row['name']}</b>\n"
                f"Дедлайн: <b>{due_local_str} {tz.key}</b>\nID: <code>{task_id}</code>",
                reply_markup=back_kb()
            )
        else:
            # если вдруг пользователь написал текст до выбора класса
            return await msg.answer("Сначала выберите класс из списка.", reply_markup=back_kb())

    # # ---------- GEN ----------
    # if mode == "gen":
    #     desc = msg.text.strip()
    #     if not desc:
    #         return await msg.answer("Опишите задачу текстом.", reply_markup=back_kb())
    #     model_name = USER_MODEL.get(msg.from_user.id, DEFAULT_MODEL)
    #     llm = build_llm(model_name)
    #     chain = PROMPT | llm | parser
    #     await msg.answer("Генерирую код, подождите 5–15 секунд...", reply_markup=back_kb())
    #     try:
    #         result = await chain.ainvoke({"task_description": desc})
    #     except Exception as e:
    #         return await msg.answer(f"Ошибка запроса к модели: {e}", reply_markup=back_kb())
    #     code = extract_code_from_markdown(result)
    #     bio = BytesIO()
    #     bio.write(code.encode("utf-8"))
    #     bio.seek(0)
    #     file = BufferedInputFile(bio.read(), filename="micropython_task.py")
    #     await msg.answer_document(file, caption="Готово! Проверьте пины и параметры.", reply_markup=back_kb())
    #     if len(result) < 3500:
    #         await msg.answer(result, reply_markup=back_kb())
    #     USER_STATE.pop(msg.from_user.id, None)
    #     return

    # Фолбэк
    USER_STATE.pop(msg.from_user.id, None)
    await show_main_menu(msg)

# ======= Коллбэки после создания ученика: пропустить/ручной вызов списка классов =======
@router.callback_query(F.data == CB_STU_AFTER_ADD_SKIP)
async def cb_stu_after_add_skip(cq: CallbackQuery):
    await cq.message.edit_text("Ок, пропускаем. Что дальше?", reply_markup=back_kb())

@router.callback_query(F.data.startswith(CB_STU_AFTER_ADD_ENROLL))
async def cb_stu_after_add_enroll(cq: CallbackQuery):
    # Этот путь оставлен на случай, если где-то вызовем отдельной кнопкой «Зачислить сейчас»
    try:
        student_id = int(cq.data.split(":")[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        s = await fetchone(db, "SELECT name, username FROM students WHERE id=?", (student_id,))
        classes = await fetchall(db, "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC")
    if not s:
        return await cq.answer("Ученик не найден", show_alert=True)
    if not classes:
        return await cq.message.edit_text("Пока нет классов. Сначала создайте класс.", reply_markup=back_kb())
    rows = [(c["name"], f"{CB_ENROLL_PICK_CLS}{student_id}:{c['id']}") for c in classes]
    rows.append(("⏭ Пропустить", CB_STU_AFTER_ADD_SKIP))
    await cq.message.edit_text(
        f"🔗 Ученик: <b>{display_student(s['name'], s['username'])}</b>\n\nВыберите <b>класс</b>:",
        reply_markup=single_col_kb(rows)
    )


# -------------------- MAIN --------------------

async def main():
    global BOT, SCHEDULER
    await ensure_db()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN в окружении")

    BOT = Bot(token=token, default=default_props)
    dp = Dispatcher()
    dp.include_router(router)

    # Планировщик напоминаний
    SCHEDULER = AsyncIOScheduler(timezone=pytz.utc)
    SCHEDULER.start()

    # Поднять незапущенные напоминания
    await rehydrate_jobs()

    print("Bot is running. Press Ctrl+C to stop.")
    await dp.start_polling(BOT)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Stopped.")
