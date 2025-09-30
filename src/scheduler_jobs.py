# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.enums import ParseMode

from config import DB_PATH, REMINDER_OFFSETS
from db import fetchone, fetchall
from utils import fmt_dt_local

BOT: Bot | None = None
SCHEDULER: AsyncIOScheduler | None = None

def set_bot(bot: Bot) -> None:
    global BOT
    BOT = bot

def set_scheduler(scheduler: AsyncIOScheduler) -> None:
    global SCHEDULER
    SCHEDULER = scheduler

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
