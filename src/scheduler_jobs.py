# -*- coding: utf-8 -*-
"""src/scheduler_jobs.py

Единая логика уведомлений/напоминаний по заданиям.

Требования:
1) При назначении задания:
   - если задание назначено группе (классу) — уведомить всех учеников этой группы;
   - если задание назначено выбранным ученикам — уведомить только их.
2) Напоминания о дедлайне:
   - за 7 дней, за 3 дня и за 24 часа до дедлайна.
3) Рассылка идёт ученикам (в ЛС), chat_id = Telegram user_id.

Технически:
- Дедлайн хранится в tasks.due_utc (ISO, UTC+5).
- Получатели хранятся в task_targets (task_id, student_id). На всякий случай есть
  fallback: если targets пусты — берём учеников по enrollments для класса.
- Планирование выполняется через APScheduler, состояния job — в таблице jobs.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import aiosqlite
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

from config import DB_PATH, REMINDER_OFFSETS, DEFAULT_TZ, DEFAULT_TZINFO
from db import fetchone, fetchall
from utils import fmt_dt_local
from callbacks import CB_BACK


BOT: Bot | None = None
SCHEDULER: AsyncIOScheduler | None = None


def _class_tz(class_row: aiosqlite.Row | dict | None) -> ZoneInfo:
    tz_name = None
    try:
        tz_name = (class_row or {}).get("timezone")  # type: ignore[attr-defined]
    except Exception:
        tz_name = None
    try:
        return ZoneInfo(tz_name or DEFAULT_TZ or DEFAULT_TZINFO.key)  # type: ignore[arg-type]
    except Exception:
        return DEFAULT_TZINFO


def _remain_text(kind: str) -> str:
    # kind ожидается из REMINDER_OFFSETS: T-7d, T-3d, T-24h
    if kind == "T-7d":
        return "7 дней"
    if kind == "T-3d":
        return "3 дня"
    if kind == "T-24h":
        return "24 часа"
    return kind


def _parse_utc(iso: str) -> datetime:
    """Parse ISO datetime and return an aware value in the default timezone (UTC+5)."""
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DEFAULT_TZINFO)
    return dt.astimezone(DEFAULT_TZINFO)


def set_bot(bot: Bot) -> None:
    global BOT
    BOT = bot


def set_scheduler(scheduler: AsyncIOScheduler) -> None:
    global SCHEDULER
    SCHEDULER = scheduler


async def init_scheduler(bot: Bot, loop: asyncio.AbstractEventLoop | None = None) -> None:
    """Создаёт AsyncIOScheduler и поднимает задачи из таблицы jobs."""
    global BOT, SCHEDULER
    BOT = bot
    if loop is None:
        loop = asyncio.get_running_loop()
    if SCHEDULER is None:
        # timezone влияет только на интерпретацию naive datetime.
        # В проекте мы работаем с aware dt для run_date и базовый пояс = UTC+5.
        try:
            tz_for_scheduler = pytz.timezone(DEFAULT_TZ or "Etc/GMT-5")
        except Exception:
            tz_for_scheduler = pytz.FixedOffset(300)  # +5h
        SCHEDULER = AsyncIOScheduler(event_loop=loop, timezone=tz_for_scheduler)
        SCHEDULER.start()

    await rehydrate_jobs()


async def _get_target_student_ids(db: aiosqlite.Connection, task_id: int, class_id: int) -> list[int]:
    db.row_factory = aiosqlite.Row

    rows = await fetchall(db, "SELECT student_id FROM task_targets WHERE task_id = ?", (task_id,))
    targets = [int(r["student_id"]) for r in rows] if rows else []
    if targets:
        return targets

    # fallback: если targets ещё не заполнены (старые данные) — берём всех учеников класса
    rows = await fetchall(db, "SELECT student_id FROM enrollments WHERE class_id = ?", (class_id,))
    return [int(r["student_id"]) for r in rows] if rows else []


async def send_task_assigned_notification(task_id: int, student_ids: list[int] | None = None) -> None:
    """Уведомление ученикам о том, что учитель назначил задание."""
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

        tz = _class_tz(class_row)
        due_utc = _parse_utc(task["due_utc"])
        due_local_str = fmt_dt_local(due_utc, tz)

        teacher_name = None
        try:
            trow = await fetchone(db, "SELECT COALESCE(name, '') AS name FROM users WHERE UserID = ?", (class_row["owner_chat_id"],))
            teacher_name = (trow["name"] or "").strip() if trow else ""
        except Exception:
            teacher_name = ""

        targets = student_ids
        if targets is None:
            targets = await _get_target_student_ids(db, task_id, class_row["id"])

    teacher_part = f"Учитель: <b>{teacher_name}</b>\n" if teacher_name else ""
    text = (
        "📌 <b>Назначено новое задание</b>\n"
        f"{teacher_part}"
        f"Группа: <b>{class_row['name']}</b>\n"
        f"Задание: <b>{task['title']}</b>\n"
        f"Дедлайн: <b>{due_local_str} {tz.key}</b>\n"
        f"\n<b>Описание:</b> {task['description'] or '—'}"
    )
    main_menu_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=CB_BACK)]
    ])

    # отправляем в ЛС ученикам; ошибки гасим, чтобы не ронять основной поток
    for uid in sorted(set(int(x) for x in (targets or []))):
        try:
            await BOT.send_message(chat_id=uid, text=text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb)
        except Exception:
            pass


async def send_task_updated_notification(task_id: int, student_ids: list[int] | None = None) -> None:
    """Уведомление ученикам: задание обновлено (название/описание/дедлайн)."""
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

        tz = _class_tz(class_row)
        due_utc = _parse_utc(task["due_utc"])
        due_local_str = fmt_dt_local(due_utc, tz)

        targets = student_ids
        if targets is None:
            targets = await _get_target_student_ids(db, task_id, class_row["id"])

    text = (
        "✏️ <b>Задание обновлено</b>\n"
        f"Группа: <b>{class_row['name']}</b>\n"
        f"Задание: <b>{task['title']}</b>\n"
        f"Дедлайн: <b>{due_local_str} {tz.key}</b>\n"
        f"\n<b>Описание:</b> {task['description'] or '—'}"
    )

    for uid in sorted(set(int(x) for x in (targets or []))):
        try:
            await BOT.send_message(chat_id=uid, text=text, parse_mode=ParseMode.HTML)
        except Exception:
            pass

async def schedule_task_jobs(task_id: int) -> None:
    """Планирует напоминания по конкретной задаче в APScheduler и фиксирует их в jobs."""
    if SCHEDULER is None:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        task = await fetchone(db, "SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not task:
            return

        due_utc = _parse_utc(task["due_utc"])

        for kind, delta in REMINDER_OFFSETS:
            run_at_utc = due_utc - delta
            if run_at_utc <= datetime.now(DEFAULT_TZINFO):
                continue

            exists = await fetchone(
                db,
                "SELECT 1 FROM jobs WHERE task_id = ? AND run_at_utc = ? AND kind = ?",
                (task_id, run_at_utc.isoformat(), kind),
            )
            if exists:
                continue

            await db.execute(
                "INSERT OR IGNORE INTO jobs(task_id, run_at_utc, kind) VALUES (?, ?, ?)",
                (task_id, run_at_utc.isoformat(), kind),
            )
            await db.commit()

            job_id = f"task{task_id}:{kind}:{int(run_at_utc.timestamp())}"
            try:
                SCHEDULER.add_job(
                    send_deadline_reminder_job,
                    "date",
                    run_date=run_at_utc,
                    args=[task_id, kind],
                    id=job_id,
                    misfire_grace_time=300,
                    replace_existing=True,
                )
            except Exception:
                pass


async def rehydrate_jobs() -> None:
    """Поднимает все будущие jobs из таблицы jobs после перезапуска бота."""
    if SCHEDULER is None:
        return

    now_iso = datetime.now(DEFAULT_TZINFO).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(db, "SELECT task_id, run_at_utc, kind FROM jobs WHERE run_at_utc > ?", (now_iso,))

    for r in rows:
        try:
            run_at_utc = _parse_utc(r["run_at_utc"])
        except Exception:
            continue
        job_id = f"rehydrated:task{r['task_id']}:{r['kind']}:{int(run_at_utc.timestamp())}"
        try:
            SCHEDULER.add_job(
                send_deadline_reminder_job,
                "date",
                run_date=run_at_utc,
                args=[int(r["task_id"]), r["kind"]],
                id=job_id,
                misfire_grace_time=300,
                replace_existing=True,
            )
        except Exception:
            pass


async def send_deadline_reminder_job(task_id: int, kind: str) -> None:
    """Отправляет напоминание ученикам о приближении дедлайна."""
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

        tz = _class_tz(class_row)
        due_utc = _parse_utc(task["due_utc"])
        due_local_str = fmt_dt_local(due_utc, tz)

        targets = await _get_target_student_ids(db, task_id, class_row["id"])

    remain = _remain_text(kind)
    text = (
        f"⏰ <b>Напоминание</b>\n"
        f"До дедлайна задания <b>{task['title']}</b> осталось <b>{remain}</b>.\n"
        f"Группа: <b>{class_row['name']}</b>\n"
        f"Дедлайн: <b>{due_local_str} {tz.key}</b>"
    )

    for uid in sorted(set(int(x) for x in (targets or []))):
        try:
            await BOT.send_message(chat_id=uid, text=text, parse_mode=ParseMode.HTML)
        except Exception:
            pass
