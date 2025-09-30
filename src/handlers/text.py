# handlers/text.py
# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import aiosqlite
import random

from aiogram import Router, F
from aiogram.types import Message

from config import DB_PATH, DEFAULT_TZ
from db import fetchone, fetchall
from keyboards import back_kb, single_col_kb
from utils import fmt_dt_local
from scheduler_jobs import schedule_task_jobs
from callbacks import (
    CB_STU_AFTER_ADD_SKIP,
    CB_ENROLL_PICK_CLS,
)

# простой in-memory FSM, как и было в проекте
USER_STATE = {}   # {user_id: {"mode": str, "step": int, "data": dict, "chat_id": int}}

router = Router()


def _gen_user_id() -> int:
    """
    В текущей схеме users.UserID НЕ автоинкремент.
    Сгенерируем положительный id. На проде лучше выделить генератор/последовательность.
    """
    return random.randint(10_000, 9_999_999)


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

    # ---------- ADD CLASS ----------
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

    # ---------- ADD STUDENT (теперь users) ----------
    if mode == "add_student":
        if step == 0:
            data["display_name"] = msg.text.strip()  # положим как name (имя/ФИО целиком)
            state["step"] = 1
            return await msg.answer(
                "Шаг 2/2: отправьте @username (или оставьте пустым — напишите «-»).\n"
                "(username теперь никуда не пишется — поле временное, для твоего удобства)",
                reply_markup=back_kb()
            )
        elif step == 1:
            # username больше никуда не сохраняем — в новой схеме его нет
            _ = msg.text.strip()

            # users требует UserID и post NOT NULL; остальное можно NULL
            new_id = _gen_user_id()
            async with aiosqlite.connect(DB_PATH) as db:
                try:
                    await db.execute(
                        "INSERT INTO users(UserID, name, post) VALUES(?, ?, ?)",
                        (new_id, data["display_name"], "student")
                    )
                    await db.commit()
                    # классы для моментального зачисления
                    db.row_factory = aiosqlite.Row
                    classes = await fetchall(db, "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC")
                except Exception as e:
                    return await msg.answer(f"Ошибка: {e}", reply_markup=back_kb())

            if not classes:
                USER_STATE.pop(msg.from_user.id, None)
                return await msg.answer(
                    f"✅ Ученик добавлен: <b>{data['display_name']}</b>\n\n"
                    f"Пока нет классов — создайте класс и запишите ученика позже.",
                    reply_markup=back_kb()
                )

            # показать список классов + «⏭ Пропустить»
            USER_STATE.pop(msg.from_user.id, None)
            rows = [(c["name"], f"{CB_ENROLL_PICK_CLS}{new_id}:{c['id']}") for c in classes]
            rows.append(("⏭ Пропустить", CB_STU_AFTER_ADD_SKIP))
            return await msg.answer(
                f"✅ Ученик добавлен: <b>{data['display_name']}</b>\n\n"
                f"Сразу записать в класс?",
                reply_markup=single_col_kb(rows)
            )

    # ---------- REGISTER ----------
    if mode == "register":
        # В новой схеме нет chat_id у пользователей.
        USER_STATE.pop(msg.from_user.id, None)
        return await msg.answer(
            "В текущей версии БД привязка чата ученика отключена (в таблице users нет chat_id).\n"
            "Если нужна — добавим отдельную таблицу, скажи.",
            reply_markup=back_kb()
        )

    # ---------- ADD TASK (класс выбран кнопкой) ----------
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
                due_utc = datetime.strptime(msg.text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            except Exception:
                return await msg.answer("❌ Некорректная дата. Нужен формат: YYYY-MM-DD HH:MM (UTC).",
                                        reply_markup=back_kb())
            data["due_utc"] = due_utc
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

    # ---------- GEN ----------
    if mode == "gen":
        desc = msg.text.strip()
        if not desc:
            return await msg.answer("Опишите задачу текстом.", reply_markup=back_kb())
        from handlers.gen import _run_generation
        USER_STATE.pop(msg.from_user.id, None)
        return await _run_generation(msg, desc)

    # fallback
    USER_STATE.pop(msg.from_user.id, None)
    from handlers.common import show_main_menu
    await show_main_menu(msg)
