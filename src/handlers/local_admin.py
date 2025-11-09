
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from utils import ensure_authorized, is_local_admin
from keyboards import (
    la_panel_kb, la_core_kb, la_info_kb, back_kb
)
from callbacks import (
    CB_LA_MENU,
    CB_LA_SEC_CORE, CB_LA_SEC_INFO,
    CB_LA_ASSIGN_TEACHER, CB_LA_ASSIGN_STUDENT,
    CB_LA_EDIT_TEACHERS, CB_LA_EDIT_STUDENTS,
    CB_LA_LIST_TEACHERS, CB_LA_LIST_STUDENTS, CB_LA_LIST_LOCAL_ADMINS,
    CB_LA_BACK_TO_CORE
)
from db import (
   create_teacher_for_school, create_student_for_school, list_teachers_for_student, 
   list_classes_for_student,  list_local_admins
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
    """Назначить ученика"""
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return

    LA_STATE[cq.from_user.id] = {"mode": "assign_student"}
    await cq.message.edit_text(
        "👦 Введите Telegram ID нового ученика (только цифры):",
        reply_markup=_back_to_core_kb()
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
    """Просмотреть список учителей"""
    if not await is_local_admin(cq.from_user.id):
        return
    try:
        teachers = await list_teachers_for_student(cq.from_user.id)
        if not teachers:
            return await cq.answer("❗ Учителей пока нет", show_alert=True)
        text = "👩‍🏫 <b>Учителя:</b>\n" + "\n".join(f"• {t}" for t in teachers)
        await cq.message.edit_text(text, reply_markup=_back_to_core_kb())
    except Exception as e:
        await cq.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == CB_LA_LIST_STUDENTS)
async def la_list_students(cq: CallbackQuery):
    """Просмотреть список учеников"""
    if not await is_local_admin(cq.from_user.id):
        return
    try:
        students = await list_classes_for_student(cq.from_user.id)
        if not students:
            return await cq.answer("❗ Учеников пока нет", show_alert=True)
        text = "👦 <b>Ученики:</b>\n" + "\n".join(f"• {s}" for s in students)
        await cq.message.edit_text(text, reply_markup=_back_to_core_kb())
    except Exception as e:
        await cq.answer(f"Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == CB_LA_LIST_LOCAL_ADMINS)
async def la_list_local_admins(cq: CallbackQuery):
    """Просмотреть список локальных администраторов"""
    if not await is_local_admin(cq.from_user.id):
        return
    try:
        admins = await list_local_admins(cq.from_user.id)
        if not admins:
            return await cq.answer("❗ Локальных администраторов пока нет", show_alert=True)
        text = "🏫 <b>Локальные администраторы:</b>\n" + "\n".join(f"• {a}" for a in admins)
        await cq.message.edit_text(text, reply_markup=_back_to_core_kb())
    except Exception as e:
        await cq.answer(f"Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == CB_LA_BACK_TO_CORE)
async def la_back_to_core(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_local_admin(cq.from_user.id):
        return
    await cq.message.edit_text("🧱 <b>Основные функции</b>\nВыберите действие:", reply_markup=la_core_kb())



# ==========================================================
#                         FSM
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
