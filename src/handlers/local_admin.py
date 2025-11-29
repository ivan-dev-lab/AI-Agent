from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import BaseFilter
from utils import ensure_authorized, is_local_admin
from keyboards import (
    la_panel_kb, la_core_kb, la_info_kb, back_kb,
    single_col_kb,          # нужно и для учителей, и для учеников
)
from handlers.text import USER_STATE
from callbacks import (
    CB_LA_MENU,
    CB_LA_SEC_CORE, CB_LA_SEC_INFO,
    CB_LA_ASSIGN_TEACHER, CB_LA_ASSIGN_STUDENT,
    CB_LA_EDIT_TEACHERS, CB_LA_EDIT_STUDENTS,
    CB_LA_LIST_TEACHERS, CB_LA_LIST_STUDENTS, CB_LA_LIST_LOCAL_ADMINS,
    CB_LA_BACK_TO_CORE, CB_LA_ASSIGN_PICK_CLS,
)
from db import (
    create_teacher_for_school,      # можно оставить, даже если потом не используем
    create_student_for_school,
    list_teachers_for_la,
    list_students_for_la,
    list_local_admins_for_la,
    create_pending_student,
    set_user_name,
    remove_teacher_from_school,
    remove_student_from_school,     # ← ДОБАВИЛИ ЭТО
    _get_school_ids_for_la,
    list_schools,
    ensure_user_with_post,
    assign_teacher_to_school,
)




router = Router()

# FSM-состояния для локального администратора
LA_STATE: dict[int, dict] = {}

class HasLaState(BaseFilter):
    async def __call__(self, msg: Message) -> bool:
        # Обрабатываем текст, только если для этого пользователя есть активное LA_STATE
        return msg.from_user.id in LA_STATE


def _back_to_core_kb():
    """Кнопка 'Назад'"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=CB_LA_BACK_TO_CORE)]
    ])


# ==========================================================
#                         ГЛАВНОЕ МЕНЮ
# ==========================================================

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


# ==========================================================
#                         ОСНОВНЫЕ
# ==========================================================

@router.callback_query(F.data == CB_LA_SEC_CORE)
async def cb_la_core(cq: CallbackQuery):
    """Меню основных функций"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    await cq.message.edit_text("🧱 <b>Основные функции</b>\nВыберите действие:", reply_markup=la_core_kb())


@router.callback_query(F.data == CB_LA_ASSIGN_TEACHER)
async def la_assign_teacher_start(cq: CallbackQuery):
    """Назначить учителя (по аналогии с global_admin, но в рамках школ ЛА)"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    # Получаем id школ, к которым привязан этот локальный администратор
    school_ids = await _get_school_ids_for_la(cq.from_user.id)
    if not school_ids:
        return await cq.message.edit_text(
            "❌ Вы не привязаны ни к одной школе. Обратитесь к глобальному администратору.",
            reply_markup=la_core_kb()
        )

    # Берём все школы и фильтруем только те, что доступны этому ЛА
    all_schools = await list_schools()
    schools = [s for s in all_schools if s["id"] in school_ids]
    if not schools:
        return await cq.message.edit_text(
            "❌ Не найдено ни одной доступной вам школы.",
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
    """После выбора школы ЛА — запрос Telegram ID учителя"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    try:
        school_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    # Проверяем, что эта школа действительно входит в список школ данного ЛА
    school_ids = await _get_school_ids_for_la(cq.from_user.id)
    if school_id not in school_ids:
        return await cq.answer("Эта школа вам недоступна.", show_alert=True)

    # Находим название школы для текста
    all_schools = await list_schools()
    school = next((s for s in all_schools if s["id"] == school_id), None)
    school_name = school["name"] if school else f"ID {school_id}"

    LA_STATE[cq.from_user.id] = {
        "mode": "assign_teacher",
        "school_id": school_id,
        "school_name": school_name,
    }

    await cq.message.edit_text(
        f"👩‍🏫 Назначение учителя в <b>{school_name}</b>\n\n"
        f"Отправьте <b>Telegram ID</b> пользователя (только цифры).",
        reply_markup=back_kb()
    )



@router.callback_query(F.data == CB_LA_ASSIGN_STUDENT)
async def la_assign_student_start(cq: CallbackQuery):
    """
    Старт мастера добавления ученика от лица локального администратора.
    Логика как в учителе: ФИО -> выбор класса -> приглашение.
    """
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    USER_STATE[cq.from_user.id] = {
        "mode": "la_assign_student",  # 👈 новый режим, который мы добавили в handlers/text.py
        "step": 0,
        "data": {},
    }

    await cq.message.edit_text(
        "👨‍🎓 <b>Добавить ученика</b>\n\n"
        "Шаг 1/2: отправьте ФИО ученика одним сообщением.",
        reply_markup=back_kb()
    )

@router.callback_query(F.data.startswith(CB_LA_ASSIGN_PICK_CLS))
async def la_assign_pick_class(cq: CallbackQuery):
    """
    Шаг 2/2: выбор класса и генерация приглашения для ученика.
    """
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    # callback_data вида "la_assign_pick_cls:<id>"
    try:
        class_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    state = USER_STATE.get(cq.from_user.id)
    if not state or state.get("mode") != "la_assign_student":
        return await cq.answer("Нет активного мастера добавления ученика", show_alert=True)

    data = state.get("data", {})
    display_name = data.get("display_name")
    if not display_name:
        return await cq.answer("Не получено имя ученика", show_alert=True)

    # создаём приглашение
    try:
        token = await create_pending_student(display_name, class_id, created_by=cq.from_user.id)
    except Exception as e:
        return await cq.message.edit_text(
            f"❌ Ошибка создания приглашения: {e}",
            reply_markup=la_core_kb()
        )

    # название класса
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT name FROM classes WHERE id = ?", (class_id,))
        row = await cur.fetchone()
        class_name = row["name"] if row else f"ID {class_id}"

    # ссылка вида https://t.me/<bot>?start=stu_<token>
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
        f"✅ Приглашение для ученика создано!\n\n"
        f"👤 <b>ФИО:</b> {display_name}\n"
        f"📁 <b>Класс:</b> {class_name}\n"
        f"🔗 <b>Ссылка:</b> {invite_link}\n\n"
        f"ℹ️ Передайте ссылку ученику. Перейдя по ней, он будет добавлен в систему "
        f"с ролью <b>student</b> и записан в выбранный класс.",
        reply_markup=la_core_kb(),
        disable_web_page_preview=True
    )



@router.callback_query(F.data == CB_LA_EDIT_TEACHERS)
async def la_edit_teachers(cq: CallbackQuery):
    """Редактирование учителей для локального админа"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    teachers = await list_teachers_for_la(cq.from_user.id)
    if not teachers:
        return await cq.message.edit_text(
            "❌ В школах, где вы являетесь локальным администратором, пока нет учителей.",
            reply_markup=la_core_kb()
        )

    # list_teachers_for_la возвращает dict с ключами UserID и name
    rows = [
        (f"{t['name']} (ID {t['UserID']})", f"la_edit_teacher_actions:{t['UserID']}")
        for t in teachers
    ]
    rows.append(("⬅ Назад", CB_LA_SEC_CORE))

    await cq.message.edit_text(
        "Выберите учителя:",
        reply_markup=single_col_kb(rows)
    )


@router.callback_query(F.data.startswith("la_edit_teacher_actions:"))
async def la_edit_teacher_actions(cq: CallbackQuery):
    """Меню действий по выбранному учителю (ЛА)"""
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
            text="🗑 Удалить из школ, где я ЛА",
            callback_data=f"la_remove_teacher:{teacher_id}"
        )],
        [InlineKeyboardButton(
            text="⬅ Назад",
            callback_data=CB_LA_EDIT_TEACHERS
        )],
    ])

    await cq.message.edit_text(
        f"Учитель ID <code>{teacher_id}</code>. Выберите действие:",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("la_rename_teacher:"))
async def la_rename_teacher(cq: CallbackQuery):
    """Запрос нового имени учителя от ЛА"""
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
        "✏️ Введите новое имя учителя:",
        reply_markup=back_kb()
    )

@router.callback_query(F.data.startswith("la_remove_teacher:"))
async def la_remove_teacher(cq: CallbackQuery):
    """Удалить учителя из всех школ, где текущий пользователь является ЛА."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    try:
        _, user_id_str = cq.data.split(":")
        teacher_id = int(user_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    # Получаем школы, где этот пользователь — ЛА
    school_ids = await _get_school_ids_for_la(cq.from_user.id)
    if not school_ids:
        return await cq.answer("Вы не привязаны ни к одной школе.", show_alert=True)

    # Отвязываем учителя от всех этих школ
    for sid in school_ids:
        await remove_teacher_from_school(sid, teacher_id)

    await cq.answer("Учитель удалён из ваших школ.")
    # Обновляем список учителей
    await la_edit_teachers(cq)


@router.callback_query(F.data == CB_LA_EDIT_STUDENTS)
async def la_edit_students(cq: CallbackQuery):
    """Редактирование учеников для локального админа"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    students = await list_students_for_la(cq.from_user.id)
    if not students:
        return await cq.message.edit_text(
            "❌ В школах, где вы являетесь локальным администратором, пока нет учеников.",
            reply_markup=la_core_kb()
        )

    # list_students_for_la возвращает dict с ключами UserID и name
    rows = [
        (f"{s['name']} (ID {s['UserID']})", f"la_edit_student_actions:{s['UserID']}")
        for s in students
    ]
    rows.append(("⬅ Назад", CB_LA_SEC_CORE))

    await cq.message.edit_text(
        "Выберите ученика:",
        reply_markup=single_col_kb(rows)
    )
@router.callback_query(F.data.startswith("la_edit_student_actions:"))
async def la_edit_student_actions(cq: CallbackQuery):
    """Меню действий по выбранному ученику (ЛА)"""
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
            text="🗑 Удалить из школ, где я ЛА",
            callback_data=f"la_remove_student:{student_id}"
        )],
        [InlineKeyboardButton(
            text="⬅ Назад",
            callback_data=CB_LA_EDIT_STUDENTS
        )],
    ])

    await cq.message.edit_text(
        f"Ученик ID <code>{student_id}</code>. Выберите действие:",
        reply_markup=kb
    )
@router.callback_query(F.data.startswith("la_rename_student:"))
async def la_rename_student(cq: CallbackQuery):
    """Запрос нового имени ученика от ЛА"""
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
        "✏️ Введите новое имя ученика:",
        reply_markup=back_kb()
    )
@router.callback_query(F.data.startswith("la_remove_student:"))
async def la_remove_student(cq: CallbackQuery):
    """Удалить ученика из всех школ, где текущий пользователь является ЛА."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    try:
        _, user_id_str = cq.data.split(":")
        student_id = int(user_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    # Получаем школы, где этот пользователь — ЛА
    school_ids = await _get_school_ids_for_la(cq.from_user.id)
    if not school_ids:
        return await cq.answer("Вы не привязаны ни к одной школе.", show_alert=True)

    # Отвязываем ученика от всех этих школ
    for sid in school_ids:
        await remove_student_from_school(sid, student_id)

    await cq.answer("Ученик удалён из ваших школ.")
    # Обновляем список учеников
    await la_edit_students(cq)



# ==========================================================
#                      ИНФОРМАЦИОННЫЕ
# ==========================================================


@router.callback_query(F.data == CB_LA_SEC_INFO)
async def cb_la_info(cq: CallbackQuery):
    """Меню информационных функций"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    await cq.message.edit_text(
        "📚 <b>Информационные функции</b>\nВыберите, что хотите просмотреть:",
        reply_markup=la_info_kb()
    )


@router.callback_query(F.data == CB_LA_LIST_TEACHERS)
async def la_list_teachers(cq: CallbackQuery):
    """Просмотреть список учителей (по школам текущего ЛА)."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    try:
        teachers = await list_teachers_for_la(cq.from_user.id)
        if not teachers:
            return await cq.answer("❗ Учителей пока нет", show_alert=True)

        lines = [
            f"• {t['name']} (ID: <code>{t['UserID']}</code>)"
            for t in teachers
        ]
        text = "👩‍🏫 <b>Учителя:</b>\n" + "\n".join(lines)
        await cq.message.edit_text(text, reply_markup=_back_to_core_kb())
    except Exception as e:
        await cq.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == CB_LA_LIST_STUDENTS)
async def la_list_students(cq: CallbackQuery):
    """Просмотреть список учеников (по школам текущего ЛА)."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    try:
        students = await list_students_for_la(cq.from_user.id)
        if not students:
            return await cq.answer("❗ Учеников пока нет", show_alert=True)

        lines = [
            f"• {s['name']} (ID: <code>{s['UserID']}</code>)"
            for s in students
        ]
        text = "👦 <b>Ученики:</b>\n" + "\n".join(lines)
        await cq.message.edit_text(text, reply_markup=_back_to_core_kb())
    except Exception as e:
        await cq.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == CB_LA_LIST_LOCAL_ADMINS)
async def la_list_local_admins(cq: CallbackQuery):
    """Просмотреть список локальных администраторов (по школам текущего ЛА)."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    try:
        admins = await list_local_admins_for_la(cq.from_user.id)
        if not admins:
            return await cq.answer("❗ Локальных администраторов пока нет", show_alert=True)

        lines = [
            f"• {a['name']} (ID: <code>{a['UserID']}</code>)"
            for a in admins
        ]
        text = "🏫 <b>Локальные администраторы:</b>\n" + "\n".join(lines)
        await cq.message.edit_text(text, reply_markup=_back_to_core_kb())
    except Exception as e:
        await cq.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == CB_LA_BACK_TO_CORE)
async def _back_to_core_kb(cq: CallbackQuery):
    """Возврат из подменю ЛА к панели разделов."""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    text = (
        "🏫 <b>Панель локального администратора</b>\n\n"
        "Выберите раздел:\n"
        "• 🧱 <b>Основные</b> — назначение и редактирование\n"
        "• 📚 <b>Информационные</b> — просмотр списков"
    )
    await cq.message.edit_text(text, reply_markup=la_panel_kb())

 

# ==========================================================
#        1                 FSM
# ==========================================================
async def _handle_la_rename_teacher_step(msg: Message, st: dict):
    """Обработка ввода нового имени учителя от ЛА"""
    new_name = msg.text.strip()
    if not new_name:
        return await msg.answer("Имя не может быть пустым. Введите имя ещё раз:")

    teacher_id = st["teacher_id"]
    await set_user_name(teacher_id, new_name)
    await msg.answer("Имя учителя обновлено.", reply_markup=la_core_kb())
    
async def _handle_la_rename_student_step(msg: Message, st: dict):
    """Обработка ввода нового имени ученика от ЛА"""
    new_name = msg.text.strip()
    if not new_name:
        return await msg.answer("Имя не может быть пустым. Введите имя ещё раз:")

    student_id = st["student_id"]
    await set_user_name(student_id, new_name)
    await msg.answer("Имя ученика обновлено.", reply_markup=la_core_kb())


@router.message(F.text, HasLaState())
async def handle_la_text_input(msg: Message):
    """Обработка текстовых шагов FSM"""
    st = LA_STATE.get(msg.from_user.id)
    if not st:
        return

    # Проверяем, что пользователь авторизован и действительно ЛА
    if not await ensure_authorized(msg.from_user.id, msg) or not await is_local_admin(msg.from_user.id):
        LA_STATE.pop(msg.from_user.id, None)
        return

    mode = st.get("mode")
    raw = msg.text.strip()

    try:
        # 👉 Переименование учителя (без проверки isdigit)
        if mode == "la_rename_teacher":
            await _handle_la_rename_teacher_step(msg, st)
            return

        # 👉 Переименование ученика (без проверки isdigit)
        if mode == "la_rename_student":
            await _handle_la_rename_student_step(msg, st)
            return

        # Для остальных режимов ожидаем Telegram ID (только цифры)
        if not raw.isdigit():
            return await msg.answer("❌ Введите корректный Telegram ID (только цифры).")

        user_id = int(raw)

        if mode == "assign_teacher":
            school_id = st.get("school_id")
            school_name = st.get("school_name", "выбранная школа")

            if school_id is None:
                return await msg.answer(
                    "❌ Не найдена школа в состоянии. Попробуйте заново через меню локального администратора.",
                    reply_markup=la_core_kb()
                )

            # Создаём/обновляем пользователя с ролью teacher
            await ensure_user_with_post(user_id, post="teacher")
            # Назначаем в выбранную школу
            await assign_teacher_to_school(school_id, user_id)

            await msg.answer(
                f"✅ Учитель <code>{user_id}</code> назначен в школу <b>{school_name}</b>.",
                reply_markup=la_core_kb()
            )


        elif mode == "assign_student":
            ok = await create_student_for_school(user_id, msg.from_user.id)
            if ok:
                await msg.answer(f"✅ Ученик <code>{user_id}</code> добавлен.", reply_markup=la_core_kb())
            else:
                await msg.answer(
                    "❌ Не удалось добавить ученика.\n"
                    "Проверьте, что вы привязаны как ЛА к школе.",
                    reply_markup=la_core_kb()
                )

        else:
            await msg.answer("❌ Неизвестный режим.")

    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")
    finally:
        # В любом случае очищаем состояние
        LA_STATE.pop(msg.from_user.id, None)
