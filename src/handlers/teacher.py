
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
import aiosqlite
from datetime import datetime

from handlers.text import USER_STATE
from config import DB_PATH
from keyboards import single_col_kb
from db import fetchall, fetchone, create_pending_student

from utils import ensure_authorized, has_post
from keyboards import back_kb, teacher_main_kb
from callbacks import (
    CB_T_ASSIGN_STUDENT, CB_T_EDIT_STUDENTS, CB_T_CREATE_GROUP,
    CB_T_EDIT_GROUP, CB_T_ADD_TASK, CB_T_LIST_TASKS, CB_BACK, CB_T_ASSIGN_PICK_CLS,
    CB_T_EDIT_PICK_CLS, CB_T_EDIT_PICK_STU, CB_T_EDIT_ACTION,
    CB_T_EDIT_PICK_NEWCLS, CB_T_EDIT_BACK_CLASSES,
    CB_T_EDIT_BACK_STUDENTS, CB_T_EDIT_BACK_ACTIONS,
    CB_T_GEDIT_PICK_CLS, CB_T_GEDIT_ACTION, CB_T_GDEL_PICK_STU,
    CB_T_GEDIT_BACK_GROUPS, CB_T_GEDIT_BACK_ACTIONS, CB_T_GEDIT_BACK_STUDENTS,
    CB_T_GADD_PICK_STU, CB_T_TASK_PICK_CLS, CB_T_TASK_SCOPE, CB_T_TASK_PICK_STU, 
    CB_T_TASK_PICK_DONE, CB_T_TASK_BACK_CLASSES, CB_T_TASK_BACK_SCOPE, CB_T_TASK_BACK_STUS,
    CB_T_VTASK_PICK_CLS, CB_T_VTASK_CLASS_MENU, CB_T_VTASK_GROUP_TASKS, CB_T_VTASK_STUDENTS,
    CB_T_VTASK_PICK_STU, CB_T_VTASK_OPEN,
    CB_T_VTASK_BACK_CLASSES, CB_T_VTASK_BACK_STUDENTS, CB_T_VTASK_BACK_TASKS,
    CB_T_VTASK_EDIT_TITLE, CB_T_VTASK_EDIT_DESC, CB_T_VTASK_EDIT_DEADLINE, CB_T_VTASK_DELETE,
)


router = Router()

from zoneinfo import ZoneInfo
from utils import fmt_dt_local
from config import DEFAULT_TZ, DEFAULT_TZINFO, DATETIME_FORMAT, DEFAULT_TZ_DISPLAY

def _format_due_simple(due_raw: str | None) -> str:
    """Форматирует дедлайн в виде dd.mm.yyyy hh:mm без вывода пояса."""
    if not due_raw:
        return "-"
    try:
        s = due_raw.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=DEFAULT_TZINFO)
        tz = ZoneInfo(DEFAULT_TZ)
        return fmt_dt_local(dt, tz)
    except Exception:
        return due_raw

async def _vt_show_classes(cq: CallbackQuery):
    """Список групп учителя для просмотра заданий."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        classes = await fetchall(
            db,
            "SELECT id, name FROM classes WHERE owner_chat_id=? ORDER BY name COLLATE NOCASE",
            (cq.from_user.id,)
        )
    if not classes:
        return await cq.message.edit_text(
            "У вас пока нет групп. Создайте группу — и задания появятся здесь.",
            reply_markup=back_kb()
        )

    rows = [(c["name"], f"{CB_T_VTASK_CLASS_MENU}{c['id']}") for c in classes]
    rows.append(("⬅ Назад", CB_BACK))
    await cq.message.edit_text("Выберите группу:", reply_markup=single_col_kb(rows))




async def _vt_show_class_menu(cq: CallbackQuery, class_id: int):
    """Меню по группе: выбор между групповыми заданиями и заданиями по ученикам."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cls = await fetchone(db, "SELECT id, name FROM classes WHERE id=? AND owner_chat_id=?", (class_id, cq.from_user.id))
    if not cls:
        return await cq.answer("Группа не найдена или принадлежит другому учителю.", show_alert=True)

    rows = [
        ("📋 Задания для всей группы", f"{CB_T_VTASK_GROUP_TASKS}{class_id}"),
        ("👥 Задания для учеников",    f"{CB_T_VTASK_STUDENTS}{class_id}"),
        ("⬅ Назад к группам",         CB_T_VTASK_BACK_CLASSES),
    ]
    await cq.message.edit_text(
        f"Группа: <b>{cls['name']}</b> Выберите, что показать:",
        reply_markup=single_col_kb(rows)
    )
async def _vt_show_students(cq: CallbackQuery, class_id: int):
    """Список учеников выбранной группы для просмотра их заданий."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cls = await fetchone(db, "SELECT id, name FROM classes WHERE id=? AND owner_chat_id=?", (class_id, cq.from_user.id))
        if not cls:
            return await cq.answer("Группа не найдена или принадлежит другому учителю.", show_alert=True)

        students = await fetchall(
            db,
            """
            SELECT u.UserID AS id, COALESCE(u.name,'(без имени)') AS name
            FROM enrollments e
            JOIN users u ON u.UserID = e.student_id
            WHERE e.class_id = ?
            ORDER BY name COLLATE NOCASE
            """,
            (class_id,)
        )
    rows = [(s["name"], f"{CB_T_VTASK_PICK_STU}{s['id']}:{class_id}") for s in students]
    rows.append(("⬅ Назад к меню группы", f"{CB_T_VTASK_CLASS_MENU}{class_id}"))

    text = f"Группа: <b>{cls['name']}</b>\n"
    text += "Выберите ученика:" if students else "В этой группе пока нет учеников."
    await cq.message.edit_text(text, reply_markup=single_col_kb(rows))




async def _vt_show_group_tasks(cq: CallbackQuery, class_id: int, desc_limit: int = 50):
    """Список заданий на всю группу."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cls = await fetchone(db, "SELECT id, name FROM classes WHERE id=? AND owner_chat_id=?", (class_id, cq.from_user.id))
        if not cls:
            return await cq.answer("Группа не найдена или принадлежит другому учителю.", show_alert=True)
        tasks = await fetchall(
            db,
            """
            SELECT id, title, COALESCE(description, '') AS description, due_utc
            FROM tasks t
            WHERE t.class_id = ?
              AND NOT EXISTS (SELECT 1 FROM task_targets x WHERE x.task_id = t.id)
            ORDER BY t.due_utc ASC
            """,
            (class_id,)
        )
    def short(text: str) -> str:
        return (text[:desc_limit] + '…') if text and len(text) > desc_limit else text

    rows = []
    lines_out = []
    for idx, t in enumerate(tasks, 1):
        desc = short(t['description'])
        try:
            due_local = _format_due_simple(t["due_utc"])
        except Exception:
            due_local = t.get("due_utc")
        suffix_desc = f" — {desc}" if desc else ""
        suffix_due = f" · {due_local}" if due_local else ""
        lines_out.append(f"{idx}. {t['title']}{suffix_due}{suffix_desc}")
        rows.append((t["title"], f"{CB_T_VTASK_OPEN}{t['id']}:0:{class_id}"))

    rows.append(("⬅ Назад к меню группы", f"{CB_T_VTASK_CLASS_MENU}{class_id}"))
    text_lines = [f"Группа: <b>{cls['name']}</b>"]
    text_lines.append("Задания для всей группы:" if tasks else "Заданий для группы пока нет.")
    if lines_out:
        text_lines.append("\n".join(lines_out))

    await cq.message.edit_text("\n".join(text_lines), reply_markup=single_col_kb(rows))

async def _vt_show_student_tasks(cq: CallbackQuery, class_id: int, student_id: int, desc_limit: int = 50):
    """Список задач ученика: только индивидуальные (target на ученика)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cls = await fetchone(db, "SELECT id, name FROM classes WHERE id=? AND owner_chat_id=?", (class_id, cq.from_user.id))
        if not cls:
            return await cq.answer("Группа не найдена или принадлежит другому учителю.", show_alert=True)

        stu = await fetchone(db, "SELECT COALESCE(name,'(без имени)') AS name FROM users WHERE UserID=?", (student_id,))
        stu_name = stu["name"] if stu else f"ID {student_id}"


        tasks = await fetchall(
            db,
            """
            SELECT DISTINCT t.id, t.title, t.description, t.due_utc, t.created_utc
            FROM tasks t
            JOIN task_targets tt ON tt.task_id = t.id AND tt.student_id = ?
            WHERE t.class_id = ?
            ORDER BY t.due_utc ASC
            """,
            (student_id, class_id)
        )

    tz = ZoneInfo(DEFAULT_TZ)
    rows = []
    lines_out: list[str] = []
    for idx, t in enumerate(tasks, 1):
        marker = "👤"
        try:
            due_local = _format_due_simple(t["due_utc"])
            suffix = f" · {due_local}" if due_local else ""
        except Exception:
            suffix = ""

        desc = t["description"] or ""
        if desc_limit and len(desc) > desc_limit:
            desc = desc[:desc_limit] + "…"

        lines_out.append(f"{idx}. {marker} {t['title']}{suffix}" + (f" — {desc}" if desc else ""))
        rows.append((t["title"], f"{CB_T_VTASK_OPEN}{t['id']}:{student_id}:{class_id}"))

    rows.append(("⬅ Назад к ученикам", f"{CB_T_VTASK_BACK_STUDENTS}{class_id}"))
    text_lines = [
        f"Группа: <b>{cls['name']}</b>",
        f"Ученик: <b>{stu_name}</b>",
    ]
    if not tasks:
        text_lines.append("Заданий не найдено.")
    else:
        text_lines.append("Задания:")
        text_lines.append("\n".join(lines_out))

    await cq.message.edit_text("\n".join(text_lines), reply_markup=single_col_kb(rows))
async def _task_show_classes(cq: CallbackQuery):
    """Список групп учителя для добавления задания."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        classes = await fetchall(
            db,
            "SELECT id, name FROM classes WHERE owner_chat_id=? ORDER BY name COLLATE NOCASE",
            (cq.from_user.id,)
        )
    if not classes:
        return await cq.message.edit_text(
            "У вас пока нет групп. Создайте группу, затем добавьте задание.",
            reply_markup=back_kb()
        )
    rows = [(c["name"], f"{CB_T_TASK_PICK_CLS}{c['id']}") for c in classes]
    rows.append(("⬅ Назад", CB_BACK))
    await cq.message.edit_text("Выберите группу для задания:", reply_markup=single_col_kb(rows))


async def _task_show_scope(cq: CallbackQuery, class_id: int):
    """Выбор охвата задания: всей группе или выбранным ученикам."""
    rows = [
        ("👥 Выдать всей группе",       f"{CB_T_TASK_SCOPE}cls:{class_id}"),
        ("👤 Выбрать учеников",         f"{CB_T_TASK_SCOPE}sel:{class_id}"),
        ("⬅ Назад к списку групп",      CB_T_TASK_BACK_CLASSES),
    ]
    await cq.message.edit_text("Кому выдать задание?", reply_markup=single_col_kb(rows))


async def _task_show_students_select(cq: CallbackQuery, class_id: int, selected: set[int] | None = None):
    """Экран мультивыбора учеников класса (переключатели)."""
    selected = selected or set()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        students = await fetchall(
            db,
            """
            SELECT u.UserID AS id, COALESCE(u.name,'(без имени)') AS name
            FROM enrollments e
            JOIN users u ON u.UserID = e.student_id
            WHERE e.class_id = ?
            ORDER BY name COLLATE NOCASE
            """,
            (class_id,)
        )
    rows = []
    for s in students:
        mark = "✅ " if s["id"] in selected else ""
        rows.append( (f"{mark}{s['name']}", f"{CB_T_TASK_PICK_STU}{s['id']}:{class_id}") )

    rows.append(("✅ Готово", f"{CB_T_TASK_PICK_DONE}{class_id}"))
    rows.append(("⬅ Назад", f"{CB_T_TASK_BACK_SCOPE}{class_id}"))

    await cq.message.edit_text(
        "Выберите учеников (нажимайте для переключения):",
        reply_markup=single_col_kb(rows)
    )


async def _show_group_list_for_edit(cq: CallbackQuery):
    """Список групп учителя для режима 'Редактировать группу'."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        classes = await fetchall(
            db,
            "SELECT id, name FROM classes WHERE owner_chat_id=? ORDER BY name COLLATE NOCASE",
            (cq.from_user.id,)
        )
    if not classes:
        return await cq.message.edit_text(
            "У вас пока нет групп. Создайте группу, затем вернитесь к редактированию.",
            reply_markup=back_kb()
        )

    rows = [(c["name"], f"{CB_T_GEDIT_PICK_CLS}{c['id']}") for c in classes]
    rows.append(("⬅ Назад", CB_BACK))
    await cq.message.edit_text(
        "Выберите группу для редактирования:",
        reply_markup=single_col_kb(rows)
    )


async def _show_group_actions(cq: CallbackQuery, class_id: int):
    """Меню действий для выбранной группы."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cls = await fetchone(
            db,
            "SELECT id, name FROM classes WHERE id=? AND owner_chat_id=?",
            (class_id, cq.from_user.id)
        )


    if not cls:
        await cq.answer("Группа не найдена или принадлежит другому учителю.", show_alert=True)
        return


    rows = [
        ("🗑 Удалить группу",        f"{CB_T_GEDIT_ACTION}delgroup:{class_id}"),
        ("👤 Удалить ученика",       f"{CB_T_GEDIT_ACTION}delstudent:{class_id}"),
        ("➕ Добавить ученика",      f"{CB_T_GEDIT_ACTION}addstudent:{class_id}"),
        ("✏️ Изменить название",     f"{CB_T_GEDIT_ACTION}rename:{class_id}"),
        ("⬅ Назад к списку групп",  CB_T_GEDIT_BACK_GROUPS),
    ]

    await cq.message.edit_text(
        f"Группа: <b>{cls['name']}</b>\nВыберите действие:",
        reply_markup=single_col_kb(rows)
    )


async def _show_students_of_group_for_delete(cq: CallbackQuery, class_id: int):
    """Список учеников выбранной группы для удаления конкретного ученика."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cls = await fetchone(db, "SELECT id, name FROM classes WHERE id=? AND owner_chat_id=?", (class_id, cq.from_user.id))
        if not cls:
            return await cq.answer("Группа не найдена или принадлежит другому учителю.", show_alert=True)

        students = await fetchall(
            db,
            """
            SELECT u.UserID AS id, COALESCE(u.name,'(без имени)') AS name
            FROM enrollments e
            JOIN users u ON u.UserID = e.student_id
            WHERE e.class_id = ?
            ORDER BY name COLLATE NOCASE
            """,
            (class_id,)
        )
    rows = [(s["name"], f"{CB_T_GDEL_PICK_STU}{s['id']}:{class_id}") for s in students]
    rows.append(("⬅ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}"))

    text = f"Группа: <b>{cls['name']}</b>\n"
    text += "Выберите ученика для удаления:" if students else "В этой группе пока нет учеников."
    await cq.message.edit_text(text, reply_markup=single_col_kb(rows))


async def _show_edit_classes(cq: CallbackQuery):
    """Показать список классов учителя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        classes = await fetchall(
            db,
            "SELECT id, name FROM classes WHERE owner_chat_id=? ORDER BY name COLLATE NOCASE",
            (cq.from_user.id,)
        )
    if not classes:
        return await cq.message.edit_text(
            "У вас пока нет групп. Создайте группу и вернитесь к редактированию.",
            reply_markup=back_kb()
        )
    rows = [(c["name"], f"{CB_T_EDIT_PICK_CLS}{c['id']}") for c in classes]
    rows.append(("⬅ Назад", CB_BACK))
    await cq.message.edit_text(
        "Выберите группу для редактирования учеников:",
        reply_markup=single_col_kb(rows)
    )


async def _show_students_of_class(cq: CallbackQuery, class_id: int):
    """Показать список учеников указанного класса."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        students = await fetchall(
            db,
            """
            SELECT u.UserID AS id, COALESCE(u.name,'(без имени)') AS name
            FROM enrollments e
            JOIN users u ON u.UserID = e.student_id
            WHERE e.class_id = ?
            ORDER BY name COLLATE NOCASE
            """,
            (class_id,)
        )
        class_row = await fetchone(db, "SELECT name FROM classes WHERE id=?", (class_id,))
        class_name = class_row["name"] if class_row else f"ID {class_id}"

    rows = [(s["name"], f"{CB_T_EDIT_PICK_STU}{s['id']}:{class_id}") for s in students]
    rows.append(("⬅ Назад к списку групп", CB_T_EDIT_BACK_CLASSES))

    text = f"Группа: <b>{class_name}</b>\n"
    if not students:
        text += "\nВ этой группе пока нет учеников."
    else:
        text += "\nВыберите ученика для редактирования:"

    await cq.message.edit_text(
        text,
        reply_markup=single_col_kb(rows)
    )


async def _show_student_actions(cq: CallbackQuery, student_id: int, class_id: int):
    """Показать меню действий над выбранным учеником."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        stu = await fetchone(db, "SELECT UserID AS id, COALESCE(name,'(без имени)') AS name FROM users WHERE UserID=?", (student_id,))
        cls = await fetchone(db, "SELECT id, name FROM classes WHERE id=?", (class_id,))
    stu_name = stu["name"] if stu else f"ID {student_id}"
    cls_name = cls["name"] if cls else f"ID {class_id}"

    rows = [
        ("✏️ Редактировать ФИО",   f"{CB_T_EDIT_ACTION}fio:{student_id}:{class_id}"),
        ("📁 Редактировать группу", f"{CB_T_EDIT_ACTION}group:{student_id}:{class_id}"),
        ("⬅ Назад к ученикам",     f"{CB_T_EDIT_BACK_STUDENTS}{class_id}"),
    ]
    await cq.message.edit_text(
        f"Ученик: <b>{stu_name}</b>\nГруппа: <b>{cls_name}</b>\n\nВыберите действие:",
        reply_markup=single_col_kb(rows)
    )



@router.callback_query(F.data == CB_BACK)
async def cb_t_back(cq: CallbackQuery):


    await cq.answer()

@router.callback_query(F.data == CB_T_ASSIGN_STUDENT)
async def cb_t_assign_student(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    USER_STATE[cq.from_user.id] = {"mode": "t_assign_student", "step": 0, "data": {}}
    await cq.message.edit_text(
        "👨‍🎓 <b>Добавить ученика</b>\n\nШаг 1/2: отправьте ФИО ученика одним сообщением.",
        reply_markup=back_kb()
    )

@router.callback_query(F.data == CB_T_EDIT_STUDENTS)
async def cb_t_edit_students(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)


    USER_STATE.pop(cq.from_user.id, None)
    await _show_edit_classes(cq)


@router.callback_query(F.data == CB_T_EDIT_BACK_CLASSES)
async def cb_t_edit_back_classes(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _show_edit_classes(cq)



@router.callback_query(F.data.startswith(CB_T_EDIT_PICK_CLS))
async def cb_t_edit_pick_cls(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _show_students_of_class(cq, class_id)



@router.callback_query(F.data.startswith(CB_T_EDIT_BACK_STUDENTS))
async def cb_t_edit_back_students(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _show_students_of_class(cq, class_id)



@router.callback_query(F.data.startswith(CB_T_EDIT_PICK_STU))
async def cb_t_edit_pick_student(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        student_id_str, class_id_str = payload.split(":")
        student_id = int(student_id_str)
        class_id = int(class_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _show_student_actions(cq, student_id, class_id)


@router.callback_query(F.data == CB_T_CREATE_GROUP)
async def cb_t_create_group(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)


    USER_STATE[cq.from_user.id] = {"mode": "add_class", "step": 0, "data": {}}
    await cq.message.edit_text(
        "📁 <b>Создать группу</b>\n\n"
        "Шаг 1/1: отправьте <b>название группы</b> одним сообщением.",
        reply_markup=back_kb()
    )



@router.callback_query(F.data.startswith(CB_T_EDIT_ACTION))
async def cb_t_edit_action(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        action, student_id_str, class_id_str = payload.split(":")
        student_id = int(student_id_str); class_id = int(class_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    if action == "fio":

        USER_STATE[cq.from_user.id] = {
            "mode": "t_edit_students_fio",
            "student_id": student_id,
            "class_id": class_id,
        }
        rows = [("⬅ Назад", f"{CB_T_EDIT_BACK_ACTIONS}{student_id}:{class_id}")]
        return await cq.message.edit_text(
            "✏️ Введите <b>новое ФИО</b> для ученика одним сообщением:",
            reply_markup=single_col_kb(rows)
        )

    elif action == "group":

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            classes = await fetchall(
                db,
                "SELECT id, name FROM classes WHERE owner_chat_id=? ORDER BY name COLLATE NOCASE",
                (cq.from_user.id,)
            )
            cur_cls = await fetchone(db, "SELECT name FROM classes WHERE id=?", (class_id,))
            cur_name = cur_cls["name"] if cur_cls else f"ID {class_id}"

        if not classes:
            return await cq.message.edit_text(
                "У вас нет доступных групп для переноса.",
                reply_markup=single_col_kb([("⬅ Назад", f"{CB_T_EDIT_BACK_ACTIONS}{student_id}:{class_id}")])
            )

        rows = []
        for c in classes:
            mark = " • (текущая)" if c["id"] == class_id else ""
            rows.append((f"{c['name']}{mark}", f"{CB_T_EDIT_PICK_NEWCLS}{c['id']}:{student_id}:{class_id}"))
        rows.append(("⬅ Назад", f"{CB_T_EDIT_BACK_ACTIONS}{student_id}:{class_id}"))

        return await cq.message.edit_text(
            f"Перенос ученика из группы <b>{cur_name}</b>.\nВыберите новую группу:",
            reply_markup=single_col_kb(rows)
        )

    else:
        return await cq.answer("Неизвестное действие", show_alert=True)




@router.callback_query(F.data.startswith(CB_T_EDIT_BACK_ACTIONS))
async def cb_t_edit_back_actions(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        student_id_str, class_id_str = payload.split(":")
        student_id = int(student_id_str); class_id = int(class_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _show_student_actions(cq, student_id, class_id)


@router.callback_query(F.data.startswith(CB_T_EDIT_PICK_NEWCLS))
async def cb_t_edit_pick_newcls(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        new_cls_str, stu_str, old_cls_str = payload.split(":")
        new_class_id = int(new_cls_str); student_id = int(stu_str); old_class_id = int(old_cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    if new_class_id == old_class_id:

        return await _show_student_actions(cq, student_id, old_class_id)

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM enrollments WHERE student_id=? AND class_id=?", (student_id, old_class_id))
            await db.execute("INSERT OR IGNORE INTO enrollments(student_id, class_id) VALUES(?,?)", (student_id, new_class_id))
            await db.commit()

            db.row_factory = aiosqlite.Row
            stu = await fetchone(db, "SELECT COALESCE(name,'(без имени)') AS name FROM users WHERE UserID=?", (student_id,))
            new_cls = await fetchone(db, "SELECT name FROM classes WHERE id=?", (new_class_id,))
            old_cls = await fetchone(db, "SELECT name FROM classes WHERE id=?", (old_class_id,))
        stu_name = stu["name"] if stu else f"ID {student_id}"
        new_name = new_cls["name"] if new_cls else f"ID {new_class_id}"
        old_name = old_cls["name"] if old_cls else f"ID {old_class_id}"

        rows = [
            ("⬅ К ученикам новой группы", f"{CB_T_EDIT_BACK_STUDENTS}{new_class_id}"),
            ("◀️ Назад к действиям",      f"{CB_T_EDIT_BACK_ACTIONS}{student_id}:{new_class_id}"),
        ]
        await cq.message.edit_text(
            f"✅ Ученик <b>{stu_name}</b> перенесён:\n<b>{old_name}</b> → <b>{new_name}</b>",
            reply_markup=single_col_kb(rows)
        )
    except Exception as e:
        await cq.message.edit_text(f"❌ Ошибка переноса: {e}", reply_markup=single_col_kb([
            ("⬅ Назад к ученикам", f"{CB_T_EDIT_BACK_STUDENTS}{old_class_id}")
        ]))


@router.callback_query(F.data == CB_T_EDIT_GROUP)
async def cb_t_edit_group(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)

    USER_STATE.pop(cq.from_user.id, None)
    await _show_group_list_for_edit(cq)


@router.callback_query(F.data == CB_T_GEDIT_BACK_GROUPS)
async def cb_t_gedit_back_groups(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _show_group_list_for_edit(cq)



@router.callback_query(F.data.startswith(CB_T_GEDIT_PICK_CLS))
async def cb_t_gedit_pick_cls(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _show_group_actions(cq, class_id)



@router.callback_query(F.data.startswith(CB_T_GEDIT_BACK_ACTIONS))
async def cb_t_gedit_back_actions(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _show_group_actions(cq, class_id)

@router.callback_query(F.data.startswith(CB_T_GEDIT_ACTION))
async def cb_t_gedit_action(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        action, cls_str = payload.split(":")
        class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)


    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cls = await fetchone(db, "SELECT id, name FROM classes WHERE id=? AND owner_chat_id=?", (class_id, cq.from_user.id))
    if not cls:
        return await cq.answer("Группа не найдена или принадлежит другому учителю.", show_alert=True)

    if action == "delgroup":

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM enrollments WHERE class_id=?", (class_id,))

                try:
                    await db.execute("DELETE FROM tasks WHERE class_id=?", (class_id,))
                except Exception:
                    pass
                await db.execute("DELETE FROM classes WHERE id=? AND owner_chat_id=?", (class_id, cq.from_user.id))
                await db.commit()
        except Exception as e:
            return await cq.message.edit_text(
                f"❌ Ошибка удаления группы: {e}",
                reply_markup=single_col_kb([("⬅ Назад к списку групп", CB_T_GEDIT_BACK_GROUPS)])
            )

        return await cq.message.edit_text(
            f"✅ Группа <b>{cls['name']}</b> удалена.\n"
            f"Ученики больше не состоят ни в какой группе (\"группа отсутствует\").",
            reply_markup=single_col_kb([("⬅ Назад к списку групп", CB_T_GEDIT_BACK_GROUPS)])
        )

    elif action == "delstudent":

        return await _show_students_of_group_for_delete(cq, class_id)

    elif action == "rename":

        USER_STATE[cq.from_user.id] = {"mode": "t_group_rename", "class_id": class_id}
        rows = [("⬅ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}")]
        return await cq.message.edit_text(
            f"✏️ Текущее название: <b>{cls['name']}</b>\nОтправьте <b>новое название</b> группы одним сообщением:",
            reply_markup=single_col_kb(rows)
        )
    elif action == "addstudent":

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            students = await fetchall(
                db,
                """
                SELECT u.UserID AS id, COALESCE(u.name,'(без имени)') AS name
                FROM users u
                WHERE u.post = 'student'
                  AND NOT EXISTS (
                      SELECT 1 FROM enrollments e
                      WHERE e.student_id = u.UserID
                        AND e.class_id = ?
                  )
                ORDER BY name COLLATE NOCASE
                """,
                (class_id,)
            )

        if not students:
            rows = [("⬅ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}")]
            return await cq.message.edit_text(
                "Нет доступных учеников для добавления в эту группу.",
                reply_markup=single_col_kb(rows)
            )

        rows = [
            (s["name"], f"{CB_T_GADD_PICK_STU}{s['id']}:{class_id}")
            for s in students
        ]
        rows.append(("⬅ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}"))

        return await cq.message.edit_text(
            "Выберите ученика для добавления в эту группу:",
            reply_markup=single_col_kb(rows)
        )


    else:
        return await cq.answer("Неизвестное действие", show_alert=True)


@router.callback_query(F.data.startswith(CB_T_GDEL_PICK_STU))
async def cb_t_gdel_pick_student(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        stu_str, cls_str = payload.split(":")
        student_id = int(stu_str); class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cls = await fetchone(db, "SELECT id, name FROM classes WHERE id=? AND owner_chat_id=?", (class_id, cq.from_user.id))
        if not cls:
            return await cq.answer("Группа не найдена или принадлежит другому учителю.", show_alert=True)

        stu = await fetchone(db, "SELECT COALESCE(name,'(без имени)') AS name FROM users WHERE UserID=?", (student_id,))
        stu_name = stu["name"] if stu else f"ID {student_id}"

        try:
            await db.execute("DELETE FROM enrollments WHERE student_id=? AND class_id=?", (student_id, class_id))
            await db.commit()
        except Exception as e:
            return await cq.message.edit_text(
                f"❌ Ошибка удаления ученика: {e}",
                reply_markup=single_col_kb([("⬅ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}")])
            )

    rows = [
        ("⬅ Назад к ученикам группы", f"{CB_T_GEDIT_BACK_STUDENTS}{class_id}"),
        ("◀️ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}"),
    ]
    await cq.message.edit_text(
        f"✅ Ученик <b>{stu_name}</b> удалён из группы <b>{cls['name']}</b>.\n"
        f"Теперь у него \"группа отсутствует\".",
        reply_markup=single_col_kb(rows)
    )

@router.callback_query(F.data.startswith(CB_T_GADD_PICK_STU))
async def cb_t_gadd_pick_student(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)

    try:
        payload = cq.data.split(":", 1)[1]
        stu_str, cls_str = payload.split(":")
        student_id = int(stu_str)
        class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cls = await fetchone(db, "SELECT id, name FROM classes WHERE id=? AND owner_chat_id=?", (class_id, cq.from_user.id))
        if not cls:
            return await cq.answer("Группа не найдена или принадлежит другому учителю.", show_alert=True)

        stu = await fetchone(db, "SELECT COALESCE(name,'(без имени)') AS name FROM users WHERE UserID=?", (student_id,))
        stu_name = stu["name"] if stu else f"ID {student_id}"

        try:

            await db.execute(
                "INSERT OR IGNORE INTO enrollments(student_id, class_id) VALUES(?, ?)",
                (student_id, class_id)
            )
            await db.commit()
        except Exception as e:
            rows = [("⬅ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}")]
            return await cq.message.edit_text(
                f"❌ Ошибка добавления ученика: {e}",
                reply_markup=single_col_kb(rows)
            )

    rows = [
        ("⬅ Назад к действиям группы", f"{CB_T_GEDIT_BACK_ACTIONS}{class_id}"),
        ("⬅ Назад к списку групп",     CB_T_GEDIT_BACK_GROUPS),
    ]
    await cq.message.edit_text(
        f"✅ Ученик <b>{stu_name}</b> добавлен в группу <b>{cls['name']}</b>.",
        reply_markup=single_col_kb(rows)
    )


@router.callback_query(F.data == CB_T_ADD_TASK)
async def cb_t_add_task(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)

    USER_STATE.pop(cq.from_user.id, None)
    await _task_show_classes(cq)

@router.callback_query(F.data == CB_T_TASK_BACK_CLASSES)
async def cb_t_task_back_classes(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _task_show_classes(cq)


@router.callback_query(F.data.startswith(CB_T_TASK_PICK_CLS))
async def cb_t_task_pick_cls(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _task_show_scope(cq, class_id)

@router.callback_query(F.data.startswith(CB_T_TASK_SCOPE))
async def cb_t_task_scope(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        scope, cls_str = payload.split(":")
        class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    if scope == "cls":

        USER_STATE[cq.from_user.id] = {
            "mode": "add_task",
            "step": 1,
            "data": {"class_id": class_id, "scope": "cls"}
        }
        return await cq.message.edit_text(
            "Шаг 2/4: отправьте <b>название задания</b> одним сообщением.",
            reply_markup=single_col_kb([("⬅ Назад", f"{CB_T_TASK_BACK_SCOPE}{class_id}")])
        )

    elif scope == "sel":

        USER_STATE[cq.from_user.id] = {
            "mode": "t_add_task_select",
            "class_id": class_id,
            "selected": set()
        }
        return await _task_show_students_select(cq, class_id, set())

    else:
        return await cq.answer("Неизвестный охват", show_alert=True)

@router.callback_query(F.data.startswith(CB_T_TASK_BACK_SCOPE))
async def cb_t_task_back_scope(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _task_show_scope(cq, class_id)

@router.callback_query(F.data.startswith(CB_T_TASK_PICK_STU))
async def cb_t_task_pick_stu(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        stu_str, cls_str = payload.split(":")
        student_id = int(stu_str); class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    st = USER_STATE.get(cq.from_user.id)
    if not st or st.get("mode") != "t_add_task_select" or st.get("class_id") != class_id:
        return await cq.answer("Нет активного выбора учеников", show_alert=True)

    selected: set[int] = st.setdefault("selected", set())
    if student_id in selected:
        selected.remove(student_id)
    else:
        selected.add(student_id)

    await _task_show_students_select(cq, class_id, selected)


@router.callback_query(F.data.startswith(CB_T_TASK_PICK_DONE))
async def cb_t_task_pick_done(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    st = USER_STATE.get(cq.from_user.id)
    if not st or st.get("mode") != "t_add_task_select" or st.get("class_id") != class_id:
        return await cq.answer("Нет активного выбора учеников", show_alert=True)

    selected = list(st.get("selected") or [])
    if not selected:
        return await cq.answer("Выберите хотя бы одного ученика", show_alert=True)


    USER_STATE[cq.from_user.id] = {
        "mode": "add_task",
        "step": 1,
        "data": {"class_id": class_id, "scope": "sel", "selected_students": selected}
    }
    await cq.message.edit_text(
        "Шаг 2/4: отправьте <b>название задания</b> одним сообщением.",
        reply_markup=single_col_kb([("⬅ Назад", f"{CB_T_TASK_BACK_STUS}{class_id}")])
    )


@router.callback_query(F.data.startswith(CB_T_TASK_BACK_STUS))
async def cb_t_task_back_stus(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    st = USER_STATE.get(cq.from_user.id)
    selected = set()
    if st and st.get("mode") in ("t_add_task_select","add_task") and st.get("class_id", st.get("data", {}).get("class_id")) == class_id:

        if st.get("mode") == "t_add_task_select":
            selected = set(st.get("selected") or [])
        elif st.get("mode") == "add_task":
            selected = set(st.get("data", {}).get("selected_students") or [])

            USER_STATE[cq.from_user.id] = {"mode": "t_add_task_select", "class_id": class_id, "selected": selected}
    else:
        USER_STATE[cq.from_user.id] = {"mode": "t_add_task_select", "class_id": class_id, "selected": set()}

    await _task_show_students_select(cq, class_id, selected)



@router.callback_query(F.data == CB_T_LIST_TASKS)
async def cb_t_list_tasks(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _vt_show_classes(cq)



@router.callback_query(F.data == CB_T_VTASK_BACK_CLASSES)
async def cb_t_vtask_back_classes(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _vt_show_classes(cq)



@router.callback_query(F.data.startswith(CB_T_VTASK_PICK_CLS))
async def cb_t_vtask_pick_cls(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _vt_show_class_menu(cq, class_id)



@router.callback_query(F.data.startswith(CB_T_VTASK_BACK_STUDENTS))
async def cb_t_vtask_back_students(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _vt_show_students(cq, class_id)



@router.callback_query(F.data.startswith(CB_T_VTASK_PICK_STU))
async def cb_t_vtask_pick_stu(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        stu_str, cls_str = payload.split(":")
        student_id = int(stu_str); class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    if student_id == 0:
        await _vt_show_group_tasks(cq, class_id)
    else:
        await _vt_show_student_tasks(cq, class_id, student_id)



@router.callback_query(F.data.startswith(CB_T_VTASK_OPEN))
async def cb_t_vtask_open(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        t_str, stu_str, cls_str = payload.split(":")
        task_id = int(t_str); student_id = int(stu_str); class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cls = await fetchone(db, "SELECT id, name FROM classes WHERE id=? AND owner_chat_id=?", (class_id, cq.from_user.id))
        if not cls:
            return await cq.answer("Группа не найдена или принадлежит другому учителю.", show_alert=True)

        t = await fetchone(
            db,
            """
            SELECT
              t.id, t.title, t.description, t.due_utc, t.created_utc,
              EXISTS (SELECT 1 FROM task_targets x WHERE x.task_id = t.id AND x.student_id = ?) AS is_for_student,
              NOT EXISTS (SELECT 1 FROM task_targets x WHERE x.task_id = t.id)                  AS is_group
            FROM tasks t
            WHERE t.id = ? AND t.class_id = ?
            """,
            (student_id, task_id, class_id)
        )
        stu = await fetchone(db, "SELECT COALESCE(name,'(без имени)') AS name FROM users WHERE UserID=?", (student_id,))

    if not t:
        return await cq.answer("Задание не найдено.", show_alert=True)

    try:
        due_str = _format_due_simple(t["due_utc"])
    except Exception:
        due_str = t["due_utc"] or "-"

    scope_note = "👥 Вся группа" if t["is_group"] else "👤 Индивидуально"
    stu_name = "Вся группа" if student_id == 0 else (stu["name"] if stu else f"ID {student_id}")

    rows = [
        ("✏️ Изменить название", f"{CB_T_VTASK_EDIT_TITLE}{task_id}:{student_id}:{class_id}"),
        ("📝 Изменить описание", f"{CB_T_VTASK_EDIT_DESC}{task_id}:{student_id}:{class_id}"),
        ("⏰ Изменить дедлайн", f"{CB_T_VTASK_EDIT_DEADLINE}{task_id}:{student_id}:{class_id}"),
        ("🗑 Удалить задание",   f"{CB_T_VTASK_DELETE}{task_id}:{student_id}:{class_id}"),
    ]
    if student_id == 0:
        rows.extend([
            ("⬅ Назад к заданиям группы", f"{CB_T_VTASK_GROUP_TASKS}{class_id}"),
            ("⬅ Назад к меню группы",     f"{CB_T_VTASK_CLASS_MENU}{class_id}"),
        ])
    else:
        rows.extend([
            ("⬅ Назад к заданиям ученика", f"{CB_T_VTASK_BACK_TASKS}{student_id}:{class_id}"),
            ("⬅ Назад к ученикам",        f"{CB_T_VTASK_BACK_STUDENTS}{class_id}"),
            ("⬅ Назад к группам",         CB_T_VTASK_BACK_CLASSES),
        ])
    await cq.message.edit_text(
        f"Группа: <b>{cls['name']}</b>\n"
        f"Ученик: <b>{stu_name}</b>\n"
        f"{scope_note}\n\n"
        f"📝 <b>{t['title']}</b>\n"
        f"⏰ Дедлайн: <b>{due_str}</b>\n\n"
        f"{t['description'] or ''}",
        reply_markup=single_col_kb(rows)
    )


@router.callback_query(F.data.startswith(CB_T_VTASK_EDIT_TITLE))
async def cb_t_vtask_edit_title(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        t_str, stu_str, cls_str = payload.split(":")
        task_id = int(t_str); student_id = int(stu_str); class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        owned = await fetchone(
            db,
            "SELECT t.id FROM tasks t JOIN classes c ON c.id=t.class_id WHERE t.id=? AND t.class_id=? AND c.owner_chat_id=?",
            (task_id, class_id, cq.from_user.id)
        )
    if not owned:
        return await cq.answer("Нет доступа к задаче.", show_alert=True)

    USER_STATE[cq.from_user.id] = {
        "mode": "t_edit_task_title",
        "task_id": task_id,
        "student_id": student_id,
        "class_id": class_id,
    }
    await cq.message.edit_text("Введите новое название задания:", reply_markup=back_kb())


@router.callback_query(F.data.startswith(CB_T_VTASK_EDIT_DESC))
async def cb_t_vtask_edit_desc(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        t_str, stu_str, cls_str = payload.split(":")
        task_id = int(t_str); student_id = int(stu_str); class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        owned = await fetchone(
            db,
            "SELECT t.id FROM tasks t JOIN classes c ON c.id=t.class_id WHERE t.id=? AND t.class_id=? AND c.owner_chat_id=?",
            (task_id, class_id, cq.from_user.id)
        )
    if not owned:
        return await cq.answer("Нет доступа к задаче.", show_alert=True)

    USER_STATE[cq.from_user.id] = {
        "mode": "t_edit_task_desc",
        "task_id": task_id,
        "student_id": student_id,
        "class_id": class_id,
    }
    await cq.message.edit_text("Введите новое описание задания (\"-\" чтобы очистить):", reply_markup=back_kb())


@router.callback_query(F.data.startswith(CB_T_VTASK_EDIT_DEADLINE))
async def cb_t_vtask_edit_deadline(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        t_str, stu_str, cls_str = payload.split(":")
        task_id = int(t_str); student_id = int(stu_str); class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        owned = await fetchone(
            db,
            "SELECT t.id FROM tasks t JOIN classes c ON c.id=t.class_id WHERE t.id=? AND t.class_id=? AND c.owner_chat_id=?",
            (task_id, class_id, cq.from_user.id)
        )
    if not owned:
        return await cq.answer("Нет доступа к задаче.", show_alert=True)

    USER_STATE[cq.from_user.id] = {
        "mode": "t_edit_task_deadline",
        "task_id": task_id,
        "student_id": student_id,
        "class_id": class_id,
    }
    await cq.message.edit_text(
        f"Введите новый дедлайн в формате {DATETIME_FORMAT} ({DEFAULT_TZ_DISPLAY}).\nНапример: 25.09.2025 18:00",
        reply_markup=back_kb()
    )


@router.callback_query(F.data.startswith(CB_T_VTASK_DELETE))
async def cb_t_vtask_delete(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        t_str, stu_str, cls_str = payload.split(":")
        task_id = int(t_str); student_id = int(stu_str); class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        owned = await fetchone(
            db,
            "SELECT t.id FROM tasks t JOIN classes c ON c.id=t.class_id WHERE t.id=? AND t.class_id=? AND c.owner_chat_id=?",
            (task_id, class_id, cq.from_user.id)
        )
        if not owned:
            return await cq.answer("Нет доступа к задаче.", show_alert=True)
        await db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        await db.commit()

    USER_STATE.pop(cq.from_user.id, None)
    await cq.answer("Задание удалено.")
    if student_id == 0:
        await _vt_show_group_tasks(cq, class_id)
    else:
        await _vt_show_student_tasks(cq, class_id, student_id)





@router.callback_query(F.data.startswith(CB_T_VTASK_CLASS_MENU))
async def cb_t_vtask_class_menu(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _vt_show_class_menu(cq, class_id)


@router.callback_query(F.data.startswith(CB_T_VTASK_GROUP_TASKS))
async def cb_t_vtask_group_tasks(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _vt_show_group_tasks(cq, class_id)


@router.callback_query(F.data.startswith(CB_T_VTASK_STUDENTS))
async def cb_t_vtask_students(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _vt_show_students(cq, class_id)

@router.callback_query(F.data.startswith(CB_T_VTASK_BACK_TASKS))
async def cb_t_vtask_back_tasks(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq): return
    if not await has_post(cq.from_user.id, "teacher"): return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        payload = cq.data.split(":", 1)[1]
        stu_str, cls_str = payload.split(":")
        student_id = int(stu_str); class_id = int(cls_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    USER_STATE.pop(cq.from_user.id, None)
    await _vt_show_student_tasks(cq, class_id, student_id)

@router.callback_query(F.data.startswith(CB_T_ASSIGN_PICK_CLS))
async def cb_t_assign_pick_class(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)


    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    state = USER_STATE.get(cq.from_user.id)
    if not state or state.get("mode") != "t_assign_student":
        return await cq.answer("Нет активного мастера добавления ученика", show_alert=True)

    display_name = state.get("data", {}).get("display_name")
    if not display_name:
        return await cq.answer("Не получено имя ученика", show_alert=True)


    try:
        token = await create_pending_student(display_name, class_id, created_by=cq.from_user.id)
    except Exception as e:
        return await cq.message.edit_text(f"❌ Ошибка создания приглашения: {e}", reply_markup=back_kb())


    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT name FROM classes WHERE id = ?", (class_id,))
        row = await cur.fetchone()
        class_name = row["name"] if row else f"ID {class_id}"

    bot_info = await cq.bot.get_me()
    bot_username = bot_info.username
    if not bot_username:
        return await cq.message.edit_text(
            "❌ У бота не установлен username. Обратитесь к разработчику.",
            reply_markup=back_kb()
        )

    invite_link = f"https://t.me/{bot_username}?start=stu_{token}"

    USER_STATE.pop(cq.from_user.id, None)
    await cq.message.edit_text(
        f"✅ Приглашение для ученика создано!\n\n"
        f"👤 <b>ФИО:</b> {display_name}\n"
        f"📁 <b>Группа:</b> {class_name}\n"
        f"🔗 <b>Ссылка:</b> {invite_link}\n\n"
        f"ℹ️ Передайте ссылку ученику. Перейдя по ней, он будет добавлен в систему с ролью "
        f"<b>student</b> и записан в выбранную группу.",
        reply_markup=teacher_main_kb(),
        disable_web_page_preview=True
    )
