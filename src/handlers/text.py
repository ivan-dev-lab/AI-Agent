# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import aiosqlite

from aiogram import Router, F
from aiogram.types import Message

from config import DB_PATH, DEFAULT_TZ
from db import fetchone
from keyboards import back_kb
from utils import parse_utc_hhmm, fmt_dt_local
from scheduler_jobs import schedule_task_jobs

# shared in-memory state (простой FSM)
USER_STATE = {}     # {user_id: {"mode": str, "step": int, "data": dict, "chat_id": int}}
USER_MODEL = {}     # если захочешь на пользователя разные модели генерации

router = Router()

@router.message(F.text)
async def on_text(msg: Message):
    state = USER_STATE.get(msg.from_user.id)
    if not state:
        # нет активного режима — покажем меню
        from handlers.common import show_main_menu
        return await show_main_menu(msg)

    mode = state["mode"]
    step = state.get("step", 0)
    data = state.setdefault("data", {})

    # -------- add_class --------
    if mode == "add_class":
        name = msg.text.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            try:
                await db.execute(
                    "INSERT INTO classes(name, owner_chat_id, timezone) VALUES (?, ?, ?)",
                    (name, msg.chat.id, DEFAULT_TZ)
                )
                await db.commit()
            except Exception as e:
                return await msg.answer(f"Ошибка создания класса: {e}", reply_markup=back_kb())
        USER_STATE.pop(msg.from_user.id, None)
        return await msg.answer(f"✅ Класс создан: <b>{name}</b> (TZ={DEFAULT_TZ})", reply_markup=back_kb())

    # -------- add_student (с предложением записать в класс) --------
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
                db.row_factory = aiosqlite.Row
                try:
                    await db.execute(
                        "INSERT INTO students(name, username) VALUES (?, ?) "
                        "ON CONFLICT(name) DO UPDATE SET username=excluded.username",
                        (data["name"], username)
                    )
                    await db.commit()
                    row = await fetchone(db, "SELECT id, name, username FROM students WHERE name=?", (data["name"],))
                    student_id = row["id"]
                    classes = await db.execute_fetchall(
                        "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC"
                    )
                except Exception as e:
                    return await msg.answer(f"Ошибка: {e}", reply_markup=back_kb())

            if not classes:
                USER_STATE.pop(msg.from_user.id, None)
                return await msg.answer(
                    f"✅ Ученик добавлен/обновлён: <b>{data['name']}</b> (@{username or '—'})\n\n"
                    f"Пока нет классов — создайте класс и запишите ученика позже.",
                    reply_markup=back_kb()
                )

            # показать список классов + «пропустить»
            from keyboards import single_col_kb
            from callbacks import CB_ENROLL_PICK_CLS, CB_STU_AFTER_ADD_SKIP
            rows = [(c["name"], f"{CB_ENROLL_PICK_CLS}{student_id}:{c['id']}") for c in classes]
            rows.append(("⏭ Пропустить", CB_STU_AFTER_ADD_SKIP))
            USER_STATE.pop(msg.from_user.id, None)
            return await msg.answer(
                f"✅ Ученик добавлен/обновлён: <b>{data['name']}</b> (@{username or '—'})\n\n"
                f"Сразу записать в класс?",
                reply_markup=single_col_kb(rows)
            )

    # -------- register (link chat) --------
    if mode == "register":
        student_name = msg.text.strip()
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("UPDATE students SET chat_id=? WHERE name=?", (msg.chat.id, student_name))
            await db.commit()
            if cur.rowcount == 0:
                return await msg.answer("Ученик не найден. Сначала добавьте его.", reply_markup=back_kb())
        USER_STATE.pop(msg.from_user.id, None)
        return await msg.answer(f"✅ Чат привязан к ученику: <b>{student_name}</b>", reply_markup=back_kb())

    # -------- add_task (класс выбран кнопкой, остались шаги 2..4) --------
    if mode == "add_task":
        if step == 1:
            data["title"] = msg.text.strip()
            state["step"] = 2
            return await msg.answer(
                "Шаг 3/4: отправьте <b>дедлайн в UTC</b> в формате <code>YYYY-MM-DD HH:MM</code>.\n"
                "Пример: <code>2025-09-25 18:00</code>",
                reply_markup=back_kb()
            )
        elif step == 2:
            try:
                data["due_utc"] = parse_utc_hhmm(msg.text)
            except Exception:
                return await msg.answer("❌ Некорректная дата. Нужен формат: YYYY-MM-DD HH:MM (UTC).",
                                        reply_markup=back_kb())
            state["step"] = 3
            return await msg.answer("Шаг 4/4: отправьте <b>описание</b> (или «-»).", reply_markup=back_kb())
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

    # -------- gen --------
    if mode == "gen":
        desc = msg.text.strip()
        if not desc:
            return await msg.answer("Опишите задачу текстом.", reply_markup=back_kb())
        # запустить генерацию (в отдельной функции модуля gen)
        from handlers.gen import _run_generation
        USER_STATE.pop(msg.from_user.id, None)
        return await _run_generation(msg, desc)

    # fallback
    USER_STATE.pop(msg.from_user.id, None)
    from handlers.common import show_main_menu
    await show_main_menu(msg)
