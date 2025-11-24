
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from utils import ensure_authorized, is_local_admin
from keyboards import (
    la_panel_kb, la_core_kb, la_info_kb, back_kb
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
    create_teacher_for_school,
    create_student_for_school,
    list_teachers_for_la,
    list_students_for_la,
    list_local_admins_for_la,
    create_pending_student,
)


router = Router()

# FSM-состояния для локального администратора
LA_STATE: dict[int, dict] = {}


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
    """Назначить учителя"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    LA_STATE[cq.from_user.id] = {"mode": "assign_teacher"}
    await cq.message.edit_text(
        "👩‍🏫 Введите Telegram ID нового учителя (только цифры):",
        reply_markup=_back_to_core_kb()
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
    """Редактировать учителей"""
    if not await is_local_admin(cq.from_user.id):
        return
    await cq.answer("🔧 Функция редактирования учителей — в разработке", show_alert=True)


@router.callback_query(F.data == CB_LA_EDIT_STUDENTS)
async def la_edit_students(cq: CallbackQuery):
    """Редактировать учеников"""
    if not await is_local_admin(cq.from_user.id):
        return
    await cq.answer("🔧 Функция редактирования учеников — в разработке", show_alert=True)


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

@router.message(F.text)
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

    if not raw.isdigit():
        return await msg.answer("❌ Введите корректный Telegram ID (только цифры).")

    user_id = int(raw)

    try:
        if mode == "assign_teacher":
            ok = await create_teacher_for_school(user_id, msg.from_user.id)
            if ok:
                await msg.answer(f"✅ Учитель <code>{user_id}</code> добавлен.", reply_markup=la_core_kb())
            else:
                await msg.answer(
                    "❌ Не удалось добавить учителя.\n"
                    "Проверьте, что вы привязаны как ЛА к школе и что такой пользователь допустим.",
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
        LA_STATE.pop(msg.from_user.id, None)
