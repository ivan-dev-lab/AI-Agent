# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import CallbackQuery
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import aiosqlite

from config import DB_PATH
from db import fetchall, fetchone
from keyboards import back_kb, single_col_kb
from callbacks import CB_ADD_TASK, CB_ADD_TASK_PICK_CLASS, CB_LIST_TASKS
from utils import fmt_dt_local
from scheduler_jobs import schedule_task_jobs

router = Router()

@router.callback_query(F.data == CB_ADD_TASK)
async def cb_add_task(cq: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        classes = await fetchall(db, "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC")
    if not classes:
        return await cq.message.edit_text(
            "📝 <b>Новое задание</b>\n\n"
            "Сначала создайте класс (меню → «🏷 Добавить класс»).",
            reply_markup=back_kb()
        )

    from handlers.text import USER_STATE
    USER_STATE[cq.from_user.id] = {"mode": "add_task", "step": 0, "data": {}, "chat_id": cq.message.chat.id}
    rows = [(c["name"], f"{CB_ADD_TASK_PICK_CLASS}{c['id']}") for c in classes]
    await cq.message.edit_text(
        "📝 <b>Новое задание</b>\n\n"
        "Шаг 1/4: выберите <b>класс</b>:",
        reply_markup=single_col_kb(rows)
    )

@router.callback_query(F.data.startswith(CB_ADD_TASK_PICK_CLASS))
async def cb_add_task_pick_class(cq: CallbackQuery):
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        class_row = await fetchone(db, "SELECT id, name, timezone FROM classes WHERE id=?", (class_id,))
    if not class_row:
        return await cq.answer("Класс не найден", show_alert=True)

    from handlers.text import USER_STATE
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
