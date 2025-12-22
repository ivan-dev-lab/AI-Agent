from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import BaseFilter

import aiosqlite

from utils import ensure_authorized, is_local_admin
from keyboards import (
    la_panel_kb, la_core_kb, la_info_kb, back_kb,
    single_col_kb,
)

from config import DB_PATH

from handlers.text import USER_STATE
from callbacks import (
    CB_LA_MENU,
    CB_LA_SEC_CORE, CB_LA_SEC_INFO,
    CB_LA_ASSIGN_TEACHER, CB_LA_ASSIGN_STUDENT,
    CB_LA_EDIT_TEACHERS, CB_LA_EDIT_STUDENTS,
    CB_LA_LIST_TEACHERS, CB_LA_LIST_STUDENTS, CB_LA_LIST_LOCAL_ADMINS,
    CB_LA_BACK_TO_CORE, CB_LA_ASSIGN_PICK_CLS, CB_LA_CREATE_SCHOOL,
)
from db import (
    create_school,
    create_teacher_for_school,
    create_student_for_school,
    list_teachers_for_la,
    list_students_for_la,
    list_local_admins_for_la,
    create_pending_student,
    set_user_name,
    remove_teacher_from_school,
    remove_student_from_school,
    _get_school_ids_for_la,
    list_schools,
    ensure_user_with_post,
    assign_teacher_to_school,
    assign_local_admin,
)





router = Router()


LA_STATE: dict[int, dict] = {}

class HasLaState(BaseFilter):
    async def __call__(self, msg: Message) -> bool:

        return msg.from_user.id in LA_STATE


def _back_to_core_kb():
    """Кнопка 'Назад'"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=CB_LA_BACK_TO_CORE)]
    ])






@router.callback_query(F.data == CB_LA_MENU)
async def cb_la_menu(cq: CallbackQuery):
    """Главное меню локального администратора"""
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await is_local_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)

    text = (
        "🏫 <b>Панель локального администратора</b>\n\n"
        "Выберите раздел:\n"
        "• 🧱 <b>Основные</b> — назначение и редактирование\n"
        "• 📚 <b>Информационные</b> — просмотр списков"
    )
    await cq.message.edit_text(text, reply_markup=la_panel_kb())
@router.callback_query(F.data == CB_LA_BACK_TO_CORE)
async def cb_la_back_to_core(cq: CallbackQuery):
    """Возврат в панель локального администратора (разделы)."""
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await is_local_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)

    text = (
        "🏫 <b>Панель локального администратора</b>\n\n"
        "Выберите раздел:\n"
        "• 🧱 <b>Основные</b> — назначение и редактирование\n"
        "• 📚 <b>Информационные</b> — просмотр списков"
    )
    await cq.message.edit_text(text, reply_markup=la_panel_kb())






@router.callback_query(F.data == CB_LA_SEC_CORE)
async def cb_la_core(cq: CallbackQuery):
    """Меню основных функций"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    await cq.message.edit_text("🧱 <b>Основные функции</b>\nВыберите действие:", reply_markup=la_core_kb())

@router.callback_query(F.data == CB_LA_CREATE_SCHOOL)
async def la_create_school_start(cq: CallbackQuery):
    """Запросить название новой школы и назначить себя админом."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    LA_STATE[cq.from_user.id] = {"mode": "la_create_school"}
    await cq.message.edit_text(
        "Введите название университета. Мы создадим его и привяжем вас как local_admin.",
        reply_markup=back_kb()
    )


@router.callback_query(F.data == CB_LA_ASSIGN_TEACHER)
async def la_assign_teacher_start(cq: CallbackQuery):
    """Назначить преподаватели для школ локального администратора."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return


    school_ids = await _get_school_ids_for_la(cq.from_user.id)
    if not school_ids:
        return await cq.message.edit_text(
            "❌ Вы не привязаны ни к одному университету. Обратитесь к администратору университета.",
            reply_markup=la_core_kb()
        )


    all_schools = await list_schools()
    schools = [s for s in all_schools if s["id"] in school_ids]
    if not schools:
        return await cq.message.edit_text(
            "❌ Не найдено ни одного доступного вам университета.",
            reply_markup=la_core_kb()
        )

    rows = [(s["name"], f"la_assign_teacher_pick:{s['id']}") for s in schools]
    rows.append(("⬅ Назад", CB_LA_SEC_CORE))

    await cq.message.edit_text(
        "Выберите учебное заведение:",
        reply_markup=single_col_kb(rows)
    )
@router.callback_query(F.data.startswith("la_assign_teacher_pick:"))
async def la_assign_teacher_pick_school(cq: CallbackQuery):
    """После выбора школы ЛА — запрос Telegram ID преподаватели"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    try:
        school_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)


    school_ids = await _get_school_ids_for_la(cq.from_user.id)
    if school_id not in school_ids:
        return await cq.answer("Этот университет вам недоступен.", show_alert=True)


    all_schools = await list_schools()
    school = next((s for s in all_schools if s["id"] == school_id), None)
    school_name = school["name"] if school else f"ID {school_id}"

    LA_STATE[cq.from_user.id] = {
        "mode": "assign_teacher",
        "step": 0,
        "school_id": school_id,
        "school_name": school_name,
    }

    await cq.message.edit_text(
        f"👩‍🏫 Назначение преподавателя в <b>{school_name}</b>\n\n"
        f"Шаг 1/2: отправьте <b>Telegram ID</b> пользователя (только цифры).",
        reply_markup=back_kb()
    )



@router.callback_query(F.data == CB_LA_ASSIGN_STUDENT)
async def la_assign_student_start(cq: CallbackQuery):
    """
    Старт мастера добавления студента от лица локального администратора.
    Логика как в преподавателе: ФИО -> выбор класса -> приглашение.
    """
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    USER_STATE[cq.from_user.id] = {
        "mode": "la_assign_student",
        "step": 0,
        "data": {},
    }

    await cq.message.edit_text(
        "👨‍🎓 <b>Добавить студента</b>\n\n"
        "Шаг 1/2: отправьте ФИО студента одним сообщением.",
        reply_markup=back_kb()
    )

@router.callback_query(F.data.startswith(CB_LA_ASSIGN_PICK_CLS))
async def la_assign_pick_class(cq: CallbackQuery):
    """
    Шаг 2/2: выбор класса и генерация приглашения для студента.
    """
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return


    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    state = USER_STATE.get(cq.from_user.id)
    if not state or state.get("mode") != "la_assign_student":
        return await cq.answer("Нет активного мастера добавления студента", show_alert=True)

    data = state.get("data", {})
    display_name = data.get("display_name")
    if not display_name:
        return await cq.answer("Не получено имя студента", show_alert=True)


    try:
        token = await create_pending_student(display_name, class_id, created_by=cq.from_user.id)
    except Exception as e:
        return await cq.message.edit_text(
            f"❌ Ошибка создания приглашения: {e}",
            reply_markup=la_core_kb()
        )


    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT name FROM classes WHERE id = ?", (class_id,))
        row = await cur.fetchone()
        class_name = row["name"] if row else f"ID {class_id}"


    bot_info = await cq.bot.get_me()
    bot_username = bot_info.username
    if not bot_username:
        USER_STATE.pop(cq.from_user.id, None)
        return await cq.message.edit_text(
            "❌ У бота не установлен username. Обратитесь к разработчику.",
            reply_markup=la_core_kb()
        )

    invite_link = f"https://t.me/{bot_username}?start=stu_{token}"

    USER_STATE.pop(cq.from_user.id, None)
    await cq.message.edit_text(
        f"✅ Приглашение для студента создано!\n\n"
        f"👤 <b>ФИО:</b> {display_name}\n"
        f"📁 <b>Класс:</b> {class_name}\n"
        f"🔗 <b>Ссылка:</b> {invite_link}\n\n"
        f"ℹ️ Передайте ссылку студенту. Перейдя по ней, он будет добавлен в систему "
        f"с ролью <b>student</b> и записан в выбранный класс.",
        reply_markup=la_core_kb(),
        disable_web_page_preview=True
    )



@router.callback_query(F.data == CB_LA_EDIT_TEACHERS)
async def la_edit_teachers(cq: CallbackQuery):
    """Редактирование преподавателей для локального админа"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    teachers = await list_teachers_for_la(cq.from_user.id)
    if not teachers:
        return await cq.message.edit_text(
            "❌ В университетах, где вы являетесь локальным администратором, пока нет преподавателей.",
            reply_markup=la_core_kb()
        )


    rows = [
        (f"{t['name']} (ID {t['UserID']})", f"la_edit_teacher_actions:{t['UserID']}")
        for t in teachers
    ]
    rows.append(("⬅ Назад", CB_LA_SEC_CORE))

    await cq.message.edit_text(
        "Выберите преподавателя:",
        reply_markup=single_col_kb(rows)
    )


@router.callback_query(F.data.startswith("la_edit_teacher_actions:"))
async def la_edit_teacher_actions(cq: CallbackQuery):
    """Меню действий по выбранному преподавателю (ЛА)"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    try:
        _, user_id_str = cq.data.split(":")
        teacher_id = int(user_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✏️ Переименовать",
            callback_data=f"la_rename_teacher:{teacher_id}"
        )],
        [InlineKeyboardButton(
            text="🗑 Удалить из университетов, где я ЛА",
            callback_data=f"la_remove_teacher:{teacher_id}"
        )],
        [InlineKeyboardButton(
            text="⬅ Назад",
            callback_data=CB_LA_EDIT_TEACHERS
        )],
    ])

    await cq.message.edit_text(
        f"Преподаватель ID <code>{teacher_id}</code>. Выберите действие:",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("la_rename_teacher:"))
async def la_rename_teacher(cq: CallbackQuery):
    """Запрос нового имени преподаватели от ЛА"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    try:
        _, user_id_str = cq.data.split(":")
        teacher_id = int(user_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    LA_STATE[cq.from_user.id] = {
        "mode": "la_rename_teacher",
        "teacher_id": teacher_id,
    }

    await cq.message.edit_text(
        "✏️ Введите новое имя преподавателя:",
        reply_markup=back_kb()
    )

@router.callback_query(F.data.startswith("la_remove_teacher:"))
async def la_remove_teacher(cq: CallbackQuery):
    """Удалить преподаватели из всех школ, где текущий пользователь является ЛА."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    try:
        _, user_id_str = cq.data.split(":")
        teacher_id = int(user_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)


    school_ids = await _get_school_ids_for_la(cq.from_user.id)
    if not school_ids:
        return await cq.answer("Вы не привязаны ни к одной университете.", show_alert=True)


    for sid in school_ids:
        await remove_teacher_from_school(sid, teacher_id)

    await cq.answer("Преподаватель удалён из ваших университетов.")

    await la_edit_teachers(cq)


@router.callback_query(F.data == CB_LA_EDIT_STUDENTS)
async def la_edit_students(cq: CallbackQuery):
    """Редактирование студентов для локального админа"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    students = await list_students_for_la(cq.from_user.id)
    if not students:
        return await cq.message.edit_text(
            "❌ В университетах, где вы являетесь локальным администратором, пока нет студентов.",
            reply_markup=la_core_kb()
        )


    rows = [
        (f"{s['name']} (ID {s['UserID']})", f"la_edit_student_actions:{s['UserID']}")
        for s in students
    ]
    rows.append(("⬅ Назад", CB_LA_SEC_CORE))

    await cq.message.edit_text(
        "Выберите студента:",
        reply_markup=single_col_kb(rows)
    )
@router.callback_query(F.data.startswith("la_edit_student_actions:"))
async def la_edit_student_actions(cq: CallbackQuery):
    """Меню действий по выбранному студенту (ЛА)"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    try:
        _, user_id_str = cq.data.split(":")
        student_id = int(user_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✏️ Переименовать",
            callback_data=f"la_rename_student:{student_id}"
        )],
        [InlineKeyboardButton(
            text="🗑 Удалить из университетов, где я ЛА",
            callback_data=f"la_remove_student:{student_id}"
        )],
        [InlineKeyboardButton(
            text="⬅ Назад",
            callback_data=CB_LA_EDIT_STUDENTS
        )],
    ])

    await cq.message.edit_text(
        f"Студент ID <code>{student_id}</code>. Выберите действие:",
        reply_markup=kb
    )
@router.callback_query(F.data.startswith("la_rename_student:"))
async def la_rename_student(cq: CallbackQuery):
    """Запрос нового имени студента от ЛА"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    try:
        _, user_id_str = cq.data.split(":")
        student_id = int(user_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    LA_STATE[cq.from_user.id] = {
        "mode": "la_rename_student",
        "student_id": student_id,
    }

    await cq.message.edit_text(
        "✏️ Введите новое имя студента:",
        reply_markup=back_kb()
    )
@router.callback_query(F.data.startswith("la_remove_student:"))
async def la_remove_student(cq: CallbackQuery):
    """Удалить студента из всех школ, где текущий пользователь является ЛА."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    try:
        _, user_id_str = cq.data.split(":")
        student_id = int(user_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)


    school_ids = await _get_school_ids_for_la(cq.from_user.id)
    if not school_ids:
        return await cq.answer("Вы не привязаны ни к одной университете.", show_alert=True)


    for sid in school_ids:
        await remove_student_from_school(sid, student_id)

    await cq.answer("Студент удалён из ваших университетов.")

    await la_edit_students(cq)








@router.callback_query(F.data == CB_LA_SEC_INFO)
async def cb_la_info(cq: CallbackQuery):
    """Меню информационных функций"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    await cq.message.edit_text(
        "📚 <b>Информационные функции</b>\nВыберите, что хотите просмотреть:",
        reply_markup=la_info_kb()
    )


def _format_la_list(title: str, icon: str, rows: list[dict], empty_text: str) -> str:
    header = f"{icon} <b>{title}</b>"
    if not rows:
        return f"{header}\n\n{empty_text}"
    lines = [
        f"{idx}. {r['name']} (ID: <code>{r['UserID']}</code>)"
        for idx, r in enumerate(rows, 1)
    ]
    return f"{header}\nВсего: <b>{len(rows)}</b>\n\n" + "\n".join(lines)


@router.callback_query(F.data == CB_LA_LIST_TEACHERS)
async def la_list_teachers(cq: CallbackQuery):
    """Просмотреть список преподавателей (по университетам текущего ЛА)."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    try:
        teachers = await list_teachers_for_la(cq.from_user.id)
        text = _format_la_list(
            title="Преподаватели",
            icon="👩‍🏫",
            rows=teachers,
            empty_text="Пока нет преподавателей в ваших университетах.",
        )
        await cq.message.edit_text(text, reply_markup=_back_to_core_kb())
    except Exception as e:
        await cq.message.edit_text(f"❌ Ошибка: {e}", reply_markup=_back_to_core_kb())


@router.callback_query(F.data == CB_LA_LIST_STUDENTS)
async def la_list_students(cq: CallbackQuery):
    """Просмотреть список студентов (по университетам текущего ЛА)."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    try:
        students = await list_students_for_la(cq.from_user.id)
        text = _format_la_list(
            title="Студенты",
            icon="👦",
            rows=students,
            empty_text="Пока нет студентов в ваших университетах.",
        )
        await cq.message.edit_text(text, reply_markup=_back_to_core_kb())
    except Exception as e:
        await cq.message.edit_text(f"❌ Ошибка: {e}", reply_markup=_back_to_core_kb())


@router.callback_query(F.data == CB_LA_LIST_LOCAL_ADMINS)
async def la_list_local_admins(cq: CallbackQuery):
    """Просмотреть список локальных администраторов (по университетам текущего ЛА)."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    try:
        admins = await list_local_admins_for_la(cq.from_user.id)
        text = _format_la_list(
            title="Локальные администраторы",
            icon="🏫",
            rows=admins,
            empty_text="Пока нет локальных администраторов в ваших университетах.",
        )
        await cq.message.edit_text(text, reply_markup=_back_to_core_kb())
    except Exception as e:
        await cq.message.edit_text(f"❌ Ошибка: {e}", reply_markup=_back_to_core_kb())



 




async def _handle_la_rename_teacher_step(msg: Message, st: dict):
    """Обработка ввода нового имени преподаватели от ЛА"""
    new_name = msg.text.strip()
    if not new_name:
        return await msg.answer("Имя не может быть пустым. Введите имя ещё раз:")

    teacher_id = st["teacher_id"]
    await set_user_name(teacher_id, new_name)
    await msg.answer("Имя преподавателя обновлено.", reply_markup=la_core_kb())
    
async def _handle_la_rename_student_step(msg: Message, st: dict):
    """Обработка ввода нового имени студента от ЛА"""
    new_name = msg.text.strip()
    if not new_name:
        return await msg.answer("Имя не может быть пустым. Введите имя ещё раз:")

    student_id = st["student_id"]
    await set_user_name(student_id, new_name)
    await msg.answer("Имя студента обновлено.", reply_markup=la_core_kb())


@router.message(F.text, HasLaState())
async def handle_la_text_input(msg: Message):
    """Обработка текстовых шагов FSM"""
    st = LA_STATE.get(msg.from_user.id)
    if not st:
        return


    if not await ensure_authorized(msg.from_user.id, msg) or not await is_local_admin(msg.from_user.id):
        LA_STATE.pop(msg.from_user.id, None)
        return

    mode = st.get("mode")
    raw = msg.text.strip()
    keep_state = False

    try:

        if mode == "la_rename_teacher":
            await _handle_la_rename_teacher_step(msg, st)
            return


        if mode == "la_rename_student":
            await _handle_la_rename_student_step(msg, st)
            return

        if mode == "la_create_school":
            name = raw
            if not name:
                return await msg.answer("Введите название университета:", reply_markup=back_kb())
            try:
                school_id = await create_school(name=name, short_name=None, address=None)
                await ensure_user_with_post(msg.from_user.id, post="local_admin", name=msg.from_user.full_name)
                await assign_local_admin(school_id, msg.from_user.id)
            except Exception as e:
                return await msg.answer(f"Не удалось создать университет: {e}", reply_markup=la_core_kb())

            await msg.answer(
                f"✅ Университет «{name}» создана. Вы назначены local_admin для неё.",
                reply_markup=la_core_kb()
            )
            return


        if mode == "assign_teacher":
            school_id = st.get("school_id")
            school_name = st.get("school_name", "выбранная университет")
            step = st.get("step", 0)

            if school_id is None:
                return await msg.answer(
                    "❌ Не найдена университет в состоянии. Попробуйте заново через меню локального администратора.",
                    reply_markup=la_core_kb()
                )

            if step == 0:
                if not raw.isdigit():
                    keep_state = True
                    return await msg.answer(
                        "❌ Введите корректный Telegram ID (только цифры).",
                        reply_markup=back_kb()
                    )

                st["teacher_id"] = int(raw)
                st["step"] = 1
                LA_STATE[msg.from_user.id] = st
                keep_state = True
                return await msg.answer(
                    "Шаг 2/2: Введите имя преподавателя:",
                    reply_markup=back_kb()
                )

            if step == 1:
                teacher_name = raw
                if not teacher_name:
                    keep_state = True
                    return await msg.answer(
                        "Введите имя преподавателя:",
                        reply_markup=back_kb()
                    )

                teacher_id = st.get("teacher_id")
                if teacher_id is None:
                    return await msg.answer(
                        "❌ Не удалось определить Telegram ID преподавателя. Попробуйте назначение заново.",
                        reply_markup=la_core_kb()
                    )

                await ensure_user_with_post(teacher_id, post="teacher", name=teacher_name)
                await assign_teacher_to_school(school_id, teacher_id)

                await msg.answer(
                    f"✅ Преподаватель <b>{teacher_name}</b> (ID <code>{teacher_id}</code>) назначен в университет <b>{school_name}</b>.",
                    reply_markup=la_core_kb()
                )
                return

        if not raw.isdigit():
            return await msg.answer("❌ Введите корректный Telegram ID (только цифры).")

        user_id = int(raw)

        if mode == "assign_student":
            ok = await create_student_for_school(user_id, msg.from_user.id)
            if ok:
                await msg.answer(f"✅ Студент <code>{user_id}</code> добавлен.", reply_markup=la_core_kb())
            else:
                await msg.answer(
                    "❌ Не удалось добавить студента.\n"
                    "Проверьте, что вы привязаны как ЛА к университете.",
                    reply_markup=la_core_kb()
                )

        else:
            await msg.answer("❌ Неизвестный режим.")

    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")
    finally:

        if not keep_state:
            LA_STATE.pop(msg.from_user.id, None)
