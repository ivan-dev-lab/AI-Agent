

from datetime import datetime
from zoneinfo import ZoneInfo
import aiosqlite
import random

from aiogram import Router, F
from aiogram.types import Message

from config import (
    DB_PATH,
    DEFAULT_TZ,
    DEFAULT_TZINFO,
    DEFAULT_TZ_DISPLAY,
    DATETIME_FORMAT,
    DATETIME_FORMAT_DISPLAY,
    LOCAL_ADMIN_PASSWORD,
)
from db import fetchone, fetchall, ensure_user_with_post
from keyboards import back_kb, single_col_kb
from utils import fmt_dt_local, get_auth_state, pop_auth_state
from scheduler_jobs import schedule_task_jobs, send_task_assigned_notification, send_task_updated_notification
from callbacks import (
    CB_STU_AFTER_ADD_SKIP,
    CB_ENROLL_PICK_CLS, CB_LA_ASSIGN_PICK_CLS,
    CB_BACK, CB_T_VTASK_OPEN,
)
from callbacks import CB_T_ASSIGN_PICK_CLS

from callbacks import (
    CB_T_EDIT_PICK_CLS, CB_T_EDIT_PICK_STU, CB_T_EDIT_BACK_STUDENTS,
    CB_T_GEDIT_BACK_GROUPS, CB_T_GEDIT_BACK_ACTIONS
)
from handlers.common import show_main_menu


USER_STATE = {}

router = Router()

async def _handle_la_password_input(msg: Message):
    """
    Handle password prompt for users not yet registered in the DB.
    When the password is correct, create a local_admin without linking to any school.
    """
    password = msg.text.strip()

    if not LOCAL_ADMIN_PASSWORD:
        pop_auth_state(msg.from_user.id)
        return await msg.answer("Пароль для доступа администратора не настроен. Сообщите об этом ответственному.")

    if password != LOCAL_ADMIN_PASSWORD:
        return await msg.answer("Пароль неверный. Попробуйте ещё раз или нажмите /start.")

    await ensure_user_with_post(
        msg.from_user.id,
        post="local_admin",
        name=msg.from_user.full_name,
    )
    pop_auth_state(msg.from_user.id)

    await msg.answer(
        "Пароль принят. Вас добавили в БД как local_admin без привязки к университете."
    )
    await show_main_menu(msg)

def _gen_user_id() -> int:
    """
    В текущей схеме users.UserID НЕ автоинкремент.
    Сгенерируем положительный id. На проде лучше выделить генератор/последовательность.
    """
    return random.randint(10_000, 9_999_999)


@router.message(F.text)
async def on_text(msg: Message):


    if get_auth_state(msg.from_user.id) == "await_la_password":
        return await _handle_la_password_input(msg)

    state = USER_STATE.get(msg.from_user.id)
    if not state:
        return await show_main_menu(msg)

    mode = state["mode"]
    step = state.get("step", 0)
    data = state.setdefault("data", {})


    if mode == "add_class":
        name = msg.text.strip()
        if not name:
            return await msg.answer(
                "❗️Название группы не может быть пустым. Введите название ещё раз:",
                reply_markup=back_kb()
            )

        async with aiosqlite.connect(DB_PATH) as db:
            try:

                await db.execute(
                    "INSERT INTO classes(name, owner_chat_id, timezone) VALUES (?, ?, ?)",
                    (name, msg.from_user.id, DEFAULT_TZ)
                )
                await db.commit()
            except aiosqlite.IntegrityError:

                return await msg.answer(
                    "❌ Группа с таким названием уже существует. Введите другое имя:",
                    reply_markup=back_kb()
                )
            except Exception as e:

                return await msg.answer(f"❌ Ошибка создания группы: {e}", reply_markup=back_kb())


        USER_STATE.pop(msg.from_user.id, None)


        return await msg.answer(
            f"✅ Группа успешно создана: <b>{name}</b>",
            reply_markup=back_kb()
        )




    if mode == "add_student":
        if step == 0:
            data["display_name"] = msg.text.strip()
            state["step"] = 1
            return await msg.answer(
                "Шаг 2/2: отправьте @username (или оставьте пустым — напишите «-»).\n"
                "(username теперь никуда не пишется — поле временное, для твоего удобства)",
                reply_markup=back_kb()
            )
        elif step == 1:

            _ = msg.text.strip()


            new_id = _gen_user_id()
            async with aiosqlite.connect(DB_PATH) as db:
                try:
                    await db.execute(
                        "INSERT INTO users(UserID, name, post) VALUES(?, ?, ?)",
                        (new_id, data["display_name"], "student")
                    )
                    await db.commit()

                    db.row_factory = aiosqlite.Row
                    classes = await fetchall(db, "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC")
                except Exception as e:
                    return await msg.answer(f"Ошибка: {e}", reply_markup=back_kb())

            if not classes:
                USER_STATE.pop(msg.from_user.id, None)
                return await msg.answer(
                    f"✅ Студент добавлен: <b>{data['display_name']}</b>\n\n"
                    f"Пока нет классов — создайте класс и запишите студента позже.",
                    reply_markup=back_kb()
                )


    if mode == "la_assign_student":
        if step == 0:
            data["display_name"] = msg.text.strip()
            state["step"] = 1


            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                classes = await fetchall(
                    db,
                    "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC"
                )

            if not classes:
                USER_STATE.pop(msg.from_user.id, None)
                return await msg.answer(
                    "Пока нет классов. Сначала создайте класс, затем повторите добавление студента.",
                    reply_markup=back_kb()
                )

            rows = [(c["name"], f"{CB_LA_ASSIGN_PICK_CLS}{c['id']}") for c in classes]
            return await msg.answer(
                "Шаг 2/2: выберите класс, в который добавить студента:",
                reply_markup=single_col_kb(rows)
            )


            USER_STATE.pop(msg.from_user.id, None)
            rows = [(c["name"], f"{CB_ENROLL_PICK_CLS}{new_id}:{c['id']}") for c in classes]
            rows.append(("⏭ Пропустить", CB_STU_AFTER_ADD_SKIP))
            return await msg.answer(
                f"✅ Студент добавлен: <b>{data['display_name']}</b>\n\n"
                f"Сразу записать в класс?",
                reply_markup=single_col_kb(rows)
            )


    if mode == "t_assign_student":
        if step == 0:
            data["display_name"] = msg.text.strip()
            state["step"] = 1


            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                classes = await fetchall(
                    db,
                    "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC"
                )

            if not classes:
                USER_STATE.pop(msg.from_user.id, None)
                return await msg.answer(
                    "Пока нет групп. Сначала создайте группу, затем повторите добавление студента.",
                    reply_markup=back_kb()
                )

            rows = [(c["name"], f"{CB_T_ASSIGN_PICK_CLS}{c['id']}") for c in classes]
            return await msg.answer(
                "Шаг 2/2: выберите группу, в которую добавить студента:",
                reply_markup=single_col_kb(rows)
            )

    if mode == "t_edit_students_fio":
        new_name = msg.text.strip()
        if not new_name:
            rows = [("⬅ Назад", f"{CB_T_EDIT_PICK_STU}{state['student_id']}:{state['class_id']}")]
            return await msg.answer("❗️ФИО не может быть пустым. Введите корректное ФИО:", reply_markup=single_col_kb(rows))

        student_id = state.get("student_id")
        class_id = state.get("class_id")
        async with aiosqlite.connect(DB_PATH) as db:
            try:
                await db.execute("UPDATE users SET name=? WHERE UserID=?", (new_name, student_id))
                await db.commit()
            except Exception as e:
                rows = [("⬅ Назад к действиям", f"{CB_T_EDIT_PICK_STU}{student_id}:{class_id}")]
                USER_STATE.pop(msg.from_user.id, None)
                return await msg.answer(f"❌ Ошибка обновления ФИО: {e}", reply_markup=single_col_kb(rows))

        USER_STATE.pop(msg.from_user.id, None)

        rows = [
            ("◀️ Продолжить редактирование этого студента", f"{CB_T_EDIT_PICK_STU}{student_id}:{class_id}"),
            ("⬅ Назад к студентам класса",                 f"{CB_T_EDIT_BACK_STUDENTS}{class_id}"),
        ]
        return await msg.answer(
            f"✅ ФИО обновлено: <b>{new_name}</b>",
            reply_markup=single_col_kb(rows)
        )

    if mode in {"t_edit_task_title", "t_edit_task_desc", "t_edit_task_deadline"}:
        task_id = state.get("task_id")
        class_id = state.get("class_id")

        if not task_id or not class_id:
            USER_STATE.pop(msg.from_user.id, None)
            return await msg.answer("❌ Не найден контекст задачи.", reply_markup=back_kb())

        raw_text = msg.text.strip()
        if mode == "t_edit_task_title" and not raw_text:
            return await msg.answer("❗️Название не может быть пустым. Введите новое название:", reply_markup=back_kb())

        if mode == "t_edit_task_desc" and raw_text == "-":
            raw_text = ""

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            owned = await fetchone(
                db,
                """
                SELECT t.id FROM tasks t
                JOIN classes c ON c.id = t.class_id
                WHERE t.id = ? AND t.class_id = ? AND c.owner_chat_id = ?
                """,
                (task_id, class_id, msg.from_user.id)
            )
            if not owned:
                USER_STATE.pop(msg.from_user.id, None)
                return await msg.answer("❌ Задача не найдена или нет прав.", reply_markup=back_kb())

            if mode == "t_edit_task_title":
                await db.execute("UPDATE tasks SET title=? WHERE id=?", (raw_text, task_id))
            elif mode == "t_edit_task_desc":
                await db.execute("UPDATE tasks SET description=? WHERE id=?", (raw_text, task_id))
            else:
                try:
                    due_utc = datetime.strptime(raw_text, DATETIME_FORMAT).replace(tzinfo=DEFAULT_TZINFO)
                except Exception:
                    return await msg.answer(
                        f"❌ Формат неверный. Используйте {DATETIME_FORMAT_DISPLAY} ({DEFAULT_TZ_DISPLAY}).",
                        reply_markup=back_kb()
                    )
                await db.execute(
                    "UPDATE tasks SET due_utc=? WHERE id=?",
                    (due_utc.astimezone(DEFAULT_TZINFO).isoformat(), task_id)
                )
            await db.commit()


            rows = await fetchall(db, "SELECT student_id FROM task_targets WHERE task_id = ?", (task_id,))
            targets = [int(r["student_id"]) for r in rows] if rows else []
            if not targets:
                rows = await fetchall(db, "SELECT student_id FROM enrollments WHERE class_id = ?", (class_id,))
                targets = [int(r["student_id"]) for r in rows] if rows else []

        kb = single_col_kb([
            ("🏠 В главное меню", CB_BACK),
            ("↩️ В меню задания", f"{CB_T_VTASK_OPEN}{task_id}:{state.get('student_id', 0)}:{class_id}"),
        ])

        USER_STATE.pop(msg.from_user.id, None)

        if targets:
            try:
                await send_task_updated_notification(task_id, targets)
            except Exception:
                pass
        return await msg.answer("✅ Задача обновлена.", reply_markup=kb)
    if mode == "t_group_rename":
        new_name = msg.text.strip()
        class_id = state.get("class_id")

        if not new_name:
            rows = [("⬅ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}")]
            return await msg.answer("❗️Название группы не может быть пустым. Введите корректное название:", reply_markup=single_col_kb(rows))


        async with aiosqlite.connect(DB_PATH) as db:
            try:
                cur = await db.execute(
                    "UPDATE classes SET name=? WHERE id=? AND owner_chat_id=?",
                    (new_name, class_id, msg.from_user.id)
                )
                await db.commit()
                if cur.rowcount == 0:
                    USER_STATE.pop(msg.from_user.id, None)
                    return await msg.answer(
                        "❌ Группа не найдена или принадлежит другому преподавателю.",
                        reply_markup=single_col_kb([("⬅ Назад к списку групп", CB_T_GEDIT_BACK_GROUPS)])
                    )
            except aiosqlite.IntegrityError:
                rows = [("⬅ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}")]
                return await msg.answer("❌ Группа с таким названием уже существует. Введите другое имя:", reply_markup=single_col_kb(rows))
            except Exception as e:
                rows = [("⬅ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}")]
                return await msg.answer(f"❌ Ошибка переименования: {e}", reply_markup=single_col_kb(rows))

        USER_STATE.pop(msg.from_user.id, None)
        rows = [
            ("◀️ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}"),
            ("⬅ Назад к списку групп",      CB_T_GEDIT_BACK_GROUPS),
        ]
        return await msg.answer(
            f"✅ Название группы изменено на: <b>{new_name}</b>",
            reply_markup=single_col_kb(rows)
        )




    if mode == "register":

        USER_STATE.pop(msg.from_user.id, None)
        return await msg.answer(
            "В текущей версии БД привязка чата студента отключена (в таблице users нет chat_id).\n"
            "Если нужна — добавим отдельную таблицу, скажи.",
            reply_markup=back_kb()
        )


    if mode == "add_task":
        if step == 1:
            data["title"] = msg.text.strip()
            state["step"] = 2
            return await msg.answer(
                f"Шаг 3/4: отправьте <b>дедлайн в {DEFAULT_TZ_DISPLAY}</b> в формате <code>{DATETIME_FORMAT_DISPLAY}</code>.\n"
                "Пример: <code>25.09.2025 18:00</code>",
                reply_markup=back_kb()
            )
        elif step == 2:
            try:
                due_utc = datetime.strptime(msg.text.strip(), DATETIME_FORMAT).replace(tzinfo=DEFAULT_TZINFO)
            except Exception:
                return await msg.answer(f"❌ Некорректная дата. Нужен формат: {DATETIME_FORMAT_DISPLAY} ({DEFAULT_TZ_DISPLAY}).",
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


                tz_name = None
                try:
                    tz_name = class_row["timezone"] if "timezone" in class_row.keys() else None
                except Exception:
                    tz_name = None
                tz = ZoneInfo((tz_name or DEFAULT_TZ))

                await db.execute(
                    "INSERT INTO tasks(class_id, title, description, due_utc, created_utc) VALUES(?, ?, ?, ?, ?)",
                    (
                        class_row["id"], data["title"], description,
                        data["due_utc"].astimezone(DEFAULT_TZINFO).isoformat(),
                        datetime.now(DEFAULT_TZINFO).isoformat()
                    )
                )
                await db.commit()
                row = await fetchone(db, "SELECT last_insert_rowid() AS id")
                task_id = row["id"]




                scope = state.get("data", {}).get("scope")
                selected_students = state.get("data", {}).get("selected_students") or []

                if scope == "sel" and selected_students:
                    target_ids = list(map(int, selected_students))

                    if target_ids:
                        pairs = [(task_id, sid) for sid in target_ids]
                        await db.executemany(
                            "INSERT OR IGNORE INTO task_targets(task_id, student_id) VALUES(?, ?)",
                            pairs,
                        )
                        await db.commit()
                else:


                    enr = await fetchall(db, "SELECT student_id FROM enrollments WHERE class_id = ?", (class_row["id"],))
                    target_ids = [int(r["student_id"]) for r in (enr or [])]


            try:
                await send_task_assigned_notification(task_id, target_ids)
            except Exception:
                pass
            await schedule_task_jobs(task_id)

            due_local_str = fmt_dt_local(data["due_utc"], tz)
            USER_STATE.pop(msg.from_user.id, None)


            scope = state.get("data", {}).get("scope")
            extra = ""
            if scope == "sel":
                extra = f"\nНазначено выбранным студентам: <b>{len(target_ids)}</b>"
            else:
                extra = f"\nНазначено всей группе: <b>{len(target_ids)}</b>"

            return await msg.answer(
                f"✅ Задание создано: <b>{data['title']}</b>\n"
                f"Класс: <b>{class_row['name']}</b>\n"
                f"Дедлайн: <b>{due_local_str}</b>\n"
                f"ID: <code>{task_id}</code>{extra}",
                reply_markup=back_kb()
            )           


    if mode == "gen":
        desc = msg.text.strip()
        if not desc:
            return await msg.answer("Опишите задачу текстом.", reply_markup=back_kb())
        from handlers.gen import _run_generation
        USER_STATE.pop(msg.from_user.id, None)
        return await _run_generation(msg, desc)


    USER_STATE.pop(msg.from_user.id, None)
    from handlers.common import show_main_menu
    await show_main_menu(msg)
