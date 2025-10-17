from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from zoneinfo import ZoneInfo

from utils import ensure_authorized, is_global_admin
from keyboards import (
    ga_panel_kb, ga_core_kb, ga_more_kb, ga_info_kb, back_kb,
    single_col_kb, ga_edit_school_detail_kb, InlineKeyboardMarkup, InlineKeyboardButton
)
from callbacks import (
    CB_GA_MENU, CB_GA_SEC_CORE, CB_GA_SEC_MORE, CB_GA_SEC_INFO,
    CB_GA_ADD_SCHOOL, CB_GA_EDIT_SCHOOLS, CB_GA_ASSIGN_LA, CB_GA_EDIT_LA,
    CB_GA_ASSIGN_TEACHER, CB_GA_ASSIGN_STUDENT, CB_GA_EDIT_TEACHERS, CB_GA_EDIT_STUDENTS,
    CB_GA_LIST_SCHOOLS, CB_GA_LIST_LA, CB_GA_LIST_TEACHERS, CB_GA_LIST_STUDENTS, CB_GA_LIST_GA,
    CB_GA_ED_S_PICK, CB_GA_ED_S_NAME, CB_GA_ED_S_SHORT, CB_GA_ED_S_ADDR, CB_GA_ED_S_TZ,
    CB_GA_BACK_TO_CORE
)
from db import (
    list_schools, get_school_by_id, update_school_field, create_school,
    create_pending_la, consume_pending_la, get_school_by_id
)


router = Router()

# Примитивное FSM для различных сценариев
GA_STATE: dict[int, dict] = {}

# FSM для активации приглашения ЛА — теперь здесь
COMMON_STATE: dict[int, dict] = {}


def _cancel_kb():
    from keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_activation")]
    ])


# --- Вспомогательная функция: кнопка "Назад в Основные" ---
def back_to_core_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в «Основные»", callback_data=CB_GA_BACK_TO_CORE)]
    ])


# --- Обработчик кнопки "Назад в Основные" ---
@router.callback_query(F.data == CB_GA_BACK_TO_CORE)
async def cb_back_to_core(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cb_ga_core(cq)


# --- Вход в панель разделов ---
@router.callback_query(F.data == CB_GA_MENU)
async def cb_ga_menu(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)

    text = (
        "📊 <b>Панель глобального администратора</b>\n\n"
        "Выберите раздел:\n"
        "• 🧱 <b>Основные</b> — УЗ и ЛА\n"
        "• 🧩 <b>Дополнительные</b> — учителя и ученики\n"
        "• 📚 <b>Информационные</b> — списки и справки"
    )
    await cq.message.edit_text(text, reply_markup=ga_panel_kb())


# --- Открытие разделов ---
@router.callback_query(F.data == CB_GA_SEC_CORE)
async def cb_ga_core(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_global_admin(cq.from_user.id):
        return
    await cq.message.edit_text("🧱 <b>Основные</b>\nВыберите действие:", reply_markup=ga_core_kb())


@router.callback_query(F.data == CB_GA_SEC_MORE)
async def cb_ga_more(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_global_admin(cq.from_user.id):
        return
    await cq.message.edit_text("🧩 <b>Дополнительные</b>\nВыберите действие:", reply_markup=ga_more_kb())


@router.callback_query(F.data == CB_GA_SEC_INFO)
async def cb_ga_info(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_global_admin(cq.from_user.id):
        return
    await cq.message.edit_text("📚 <b>Информационные</b>\nЧто показать:", reply_markup=ga_info_kb())


# --- Добавление УЗ: запуск мастера ---
@router.callback_query(F.data == CB_GA_ADD_SCHOOL)
async def ga_add_school(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)

    GA_STATE[cq.from_user.id] = {"mode": "ga_add_school", "step": 0, "data": {}}
    await cq.message.edit_text(
        "🏫 <b>Добавление учебного заведения</b>\n\n"
        "Шаг 1/4: отправьте <b>полное название</b> УЗ.\n",
        reply_markup=back_kb()
    )


# --- Редактирование УЗ: выбор из списка ---
@router.callback_query(F.data == CB_GA_EDIT_SCHOOLS)
async def ga_edit_schools(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_global_admin(cq.from_user.id):
        return
    schools = await list_schools()
    if not schools:
        return await cq.message.edit_text(
            "Пока нет учебных заведений.\nСоздайте одно в разделе «Основные».",
            reply_markup=ga_core_kb()
        )
    rows = [(f"{s['name']}", f"{CB_GA_ED_S_PICK}{s['id']}") for s in schools]
    rows.append(("⬅️ Назад в «Основные»", CB_GA_BACK_TO_CORE))
    await cq.message.edit_text("Выберите УЗ для редактирования:", reply_markup=single_col_kb(rows))


@router.callback_query(F.data.startswith(CB_GA_ED_S_PICK))
async def ga_es_pick(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)

    try:
        school_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    s = await get_school_by_id(school_id)
    if not s:
        return await cq.answer("УЗ не найдено (возможно, удалено).", show_alert=True)

    await cq.message.edit_text(_format_school_card(s), reply_markup=ga_edit_school_detail_kb(school_id))


def _format_school_card(s: dict) -> str:
    return (
        "🏫 <b>Учебное заведение</b>\n\n"
        f"ID: <code>{s['id']}</code>\n"
        f"Название: <b>{s['name']}</b>\n"
        f"Краткое имя: <b>{s.get('short_name') or '—'}</b>\n"
        f"Адрес: <b>{s.get('address') or '—'}</b>\n"
        f"Таймзона: <code>{s.get('timezone') or 'UTC'}</code>"
    )


def _start_edit_field(user_id: int, school_id: int, field: str, prompt: str):
    GA_STATE[user_id] = {"mode": "ga_edit_school", "school_id": school_id, "field": field}
    return prompt


@router.callback_query(F.data.startswith(CB_GA_ED_S_NAME))
async def ga_es_name(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)
    sid = int(cq.data.split(":", 1)[1])
    txt = _start_edit_field(cq.from_user.id, sid, "name", "Введите новое <b>название</b> УЗ:")
    await cq.message.edit_text(txt, reply_markup=ga_edit_school_detail_kb(sid))


@router.callback_query(F.data.startswith(CB_GA_ED_S_SHORT))
async def ga_es_short(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)
    sid = int(cq.data.split(":", 1)[1])
    txt = _start_edit_field(cq.from_user.id, sid, "short_name",
                            "Введите <b>краткое имя</b> УЗ (или «-» чтобы очистить):")
    await cq.message.edit_text(txt, reply_markup=ga_edit_school_detail_kb(sid))


@router.callback_query(F.data.startswith(CB_GA_ED_S_ADDR))
async def ga_es_addr(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)
    sid = int(cq.data.split(":", 1)[1])
    txt = _start_edit_field(cq.from_user.id, sid, "address",
                            "Введите <b>адрес</b> УЗ (или «-» чтобы очистить):")
    await cq.message.edit_text(txt, reply_markup=ga_edit_school_detail_kb(sid))


@router.callback_query(F.data.startswith(CB_GA_ED_S_TZ))
async def ga_es_tz(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)
    sid = int(cq.data.split(":", 1)[1])
    txt = _start_edit_field(cq.from_user.id, sid, "timezone",
                            "Введите <b>IANA таймzonу</b> (например, <code>Europe/Moscow</code>)\n"
                            "Или «-» для <code>UTC</code>.")
    await cq.message.edit_text(txt, reply_markup=ga_edit_school_detail_kb(sid))


# --- Назначение локального администратора (через приглашение) ---
@router.callback_query(F.data == CB_GA_ASSIGN_LA)
async def ga_assign_la_start(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_global_admin(cq.from_user.id):
        return

    schools = await list_schools()
    if not schools:
        return await cq.message.edit_text(
            "❌ Нет учебных заведений. Сначала создайте хотя бы одно.",
            reply_markup=ga_core_kb()
        )

    rows = [(f"{s['name']}", f"ga_assign_la_pick:{s['id']}") for s in schools]
    rows.append(("⬅️ Назад в «Основные»", CB_GA_BACK_TO_CORE))
    await cq.message.edit_text(
        "Выберите учебное заведение, для которого создаётся приглашение ЛА:",
        reply_markup=single_col_kb(rows)
    )


@router.callback_query(F.data.startswith("ga_assign_la_pick:"))
async def ga_assign_la_pick_school(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)

    try:
        school_id = int(cq.data.split(":", 1)[1])
    except ValueError:
        return await cq.answer("Некорректный ID школы", show_alert=True)

    school = await get_school_by_id(school_id)
    if not school:
        return await cq.answer("УЗ не найдено", show_alert=True)

    GA_STATE[cq.from_user.id] = {
        "mode": "ga_assign_la_invite",
        "school_id": school_id,
        "school_name": school["name"]
    }

    await cq.message.edit_text(
        f"📬 Создание приглашения для ЛА в <b>{school['name']}</b>\n\n"
        "Отправьте <b>Telegram ID</b> будущего локального администратора (только цифры).",
        reply_markup=back_to_core_kb()
    )


# --- Обработка текстовых сообщений (все FSM) ---
@router.message(F.text)
async def handle_ga_text_input(msg: Message):
    user_id = msg.from_user.id

    # Сначала проверяем FSM для активации ЛА (COMMON_STATE)
    st_common = COMMON_STATE.get(user_id)
    if st_common and st_common.get("mode") == "await_la_password":
        await _handle_la_password_input(msg, st_common)
        return

    # Затем проверяем FSM для админки (GA_STATE)
    st = GA_STATE.get(user_id)
    if not st:
        return

    mode = st.get("mode")

    if not await ensure_authorized(user_id, msg) or not await is_global_admin(user_id):
        GA_STATE.pop(user_id, None)
        return

    if mode == "ga_add_school":
        await _handle_ga_add_school_step(msg, st)
    elif mode == "ga_edit_school":
        await _handle_ga_edit_school_step(msg, st)
    elif mode == "ga_assign_la_invite":
        await _handle_la_invite_step(msg, st)
    else:
        GA_STATE.pop(user_id, None)


# --- Обработка ввода пароля при активации ЛА ---
async def _handle_la_password_input(msg: Message, st: dict):
    password = msg.text.strip()
    user_id = msg.from_user.id

    school_id = await consume_pending_la(user_id, password)
    COMMON_STATE.pop(user_id, None)

    if school_id is not None:
        school = await get_school_by_id(school_id)
        school_name = school["name"] if school else "неизвестное"
        await msg.answer(
            "🎉 <b>Поздравляем!</b>\n\n"
            "Вы успешно активировали роль <b>локального администратора</b>.\n"
            f"🏫 Учебное заведение: <b>{school_name}</b>"
        )
        # Показываем главное меню (в common.py)
        from handlers.common import _show_main_for
        await _show_main_for(user_id, msg)
    else:
        await msg.answer(
            "❌ Неверный пароль или приглашение устарело.\n"
            "Обратитесь к глобальному администратору.",
            reply_markup=_cancel_kb()
        )


# --- Обработка шагов приглашения ЛА ---
async def _handle_la_invite_step(msg: Message, st: dict):
    user_id = msg.from_user.id
    school_id = st["school_id"]
    school_name = st["school_name"]
    raw = msg.text.strip()

    if not raw.isdigit():
        return await msg.answer(
            "❌ Некорректный Telegram ID. Отправьте только цифры.",
            reply_markup=back_to_core_kb()
        )

    target_user_id = int(raw)

    try:
        password = await create_pending_la(target_user_id, school_id)
    except Exception as e:
        GA_STATE.pop(user_id, None)
        return await msg.answer(f"❌ Ошибка генерации приглашения: {e}", reply_markup=ga_core_kb())

    bot_info = await msg.bot.get_me()
    bot_username = bot_info.username

    if not bot_username:
        GA_STATE.pop(user_id, None)
        return await msg.answer(
            "❌ У бота не установлен username. Обратитесь к разработчику.",
            reply_markup=ga_core_kb()
        )

    invite_link = f"https://t.me/{bot_username}?start={target_user_id}"

    GA_STATE.pop(user_id, None)

    await msg.answer(
        f"✅ Приглашение для ЛА создано!\n\n"
        f"👤 <b>Telegram ID:</b> <code>{target_user_id}</code>\n"
        f"🏫 <b>Учебное заведение:</b> {school_name}\n\n"
        f"🔑 <b>Пароль:</b> <code>{password}</code>\n"
        f"🔗 <b>Ссылка:</b> {invite_link}\n\n"
        f"ℹ️ Перешлите <b>ссылку</b> и <b>пароль</b> пользователю.\n"
        f"Только он сможет активировать приглашение.",
        reply_markup=ga_core_kb(),
        disable_web_page_preview=True
    )


# --- Обработка шагов добавления УЗ ---
async def _handle_ga_add_school_step(msg: Message, st: dict):
    step = st.get("step", 0)
    data = st.setdefault("data", {})
    user_id = msg.from_user.id

    if step == 0:
        data["name"] = msg.text.strip()
        st["step"] = 1
        return await msg.answer(
            "Шаг 2/4: отправьте <b>краткое имя</b> УЗ (или «-», чтобы пропустить).",
            reply_markup=back_kb()
        )

    if step == 1:
        short = msg.text.strip()
        data["short_name"] = None if short == "-" else short
        st["step"] = 2
        return await msg.answer(
            "Шаг 3/4: отправьте <b>адрес</b> УЗ (или «-», чтобы пропустить).",
            reply_markup=back_kb()
        )

    if step == 2:
        addr = msg.text.strip()
        data["address"] = None if addr == "-" else addr
        st["step"] = 3
        return await msg.answer(
            "Шаг 4/4: отправьте <b>IANA таймзону</b> (например, <code>Europe/Moscow</code>)\n"
            "или «-» для <b>UTC</b>.",
            reply_markup=back_kb()
        )

    if step == 3:
        tz_in = msg.text.strip()
        tz = "UTC" if tz_in == "-" else tz_in
        try:
            _ = ZoneInfo(tz)
        except Exception:
            tz = "UTC"

        try:
            school_id = await create_school(
                name=data["name"],
                short_name=data.get("short_name"),
                address=data.get("address"),
                tz=tz
            )
        except Exception as e:
            GA_STATE.pop(user_id, None)
            return await msg.answer(f"❌ Ошибка создания УЗ: {e}", reply_markup=ga_core_kb())

        GA_STATE.pop(user_id, None)
        text = (
            "✅ <b>Учебное заведение создано</b>\n\n"
            f"ID: <code>{school_id}</code>\n"
            f"Название: <b>{data['name']}</b>\n"
            f"Краткое имя: <b>{data.get('short_name') or '—'}</b>\n"
            f"Адрес: <b>{data.get('address') or '—'}</b>\n"
            f"Таймзона: <b>{tz}</b>\n\n"
            "Что дальше?"
        )
        return await msg.answer(text, reply_markup=ga_core_kb())


# --- Обработка шагов редактирования УЗ ---
async def _handle_ga_edit_school_step(msg: Message, st: dict):
    user_id = msg.from_user.id
    school_id = st["school_id"]
    field = st["field"]
    raw = msg.text.strip()

    if field == "name":
        if len(raw) < 2:
            return await msg.answer("❌ Название слишком короткое.")
        value = raw
    elif field in ("short_name", "address"):
        value = None if raw == "-" else raw
    elif field == "timezone":
        value = "UTC" if raw == "-" else raw
        try:
            _ = ZoneInfo(value)
        except Exception:
            return await msg.answer("❌ Некорректная таймзона. Пример: <code>Europe/Moscow</code> или «-».")
    else:
        GA_STATE.pop(user_id, None)
        return await msg.answer("❌ Неизвестное поле для редактирования.")

    try:
        await update_school_field(school_id, field, value)
    except Exception as e:
        GA_STATE.pop(user_id, None)
        return await msg.answer(f"❌ Ошибка сохранения: {e}")

    s = await get_school_by_id(school_id)
    GA_STATE.pop(user_id, None)
    if not s:
        return await msg.answer("⚠️ УЗ не найдено после обновления (удалено?)")

    await msg.answer("✅ Изменения сохранены.")
    await msg.answer(_format_school_card(s), reply_markup=ga_edit_school_detail_kb(school_id))


# --- Заглушки ---
@router.callback_query(F.data == CB_GA_EDIT_LA)
async def ga_edit_la(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cq.answer("Редактирование ЛА — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_ASSIGN_TEACHER)
async def ga_assign_teacher(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cq.answer("Назначить учителя — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_ASSIGN_STUDENT)
async def ga_assign_student(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cq.answer("Назначить ученика — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_EDIT_TEACHERS)
async def ga_edit_teachers(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cq.answer("Редактирование учителей — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_EDIT_STUDENTS)
async def ga_edit_students(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cq.answer("Редактирование учеников — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_LIST_SCHOOLS)
async def ga_list_schools(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cq.answer("Список УЗ — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_LIST_LA)
async def ga_list_la(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cq.answer("Список ЛА — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_LIST_TEACHERS)
async def ga_list_teachers(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cq.answer("Список учителей — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_LIST_STUDENTS)
async def ga_list_students(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cq.answer("Список учеников — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_LIST_GA)
async def ga_list_ga(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    await cq.answer("Список глобальных админов — скоро ✨", show_alert=True)