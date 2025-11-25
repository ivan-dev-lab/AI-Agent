from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import BaseFilter
from zoneinfo import ZoneInfo
import aiosqlite
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
    create_pending_la, consume_pending_la, fetchall
)

# === Доп. импорты для новых сценариев (учителя/ученики/списки) ===
from db import (
    assign_teacher_to_school, assign_student_to_school,
    remove_teacher_from_school, remove_student_from_school,
    list_school_teachers, list_school_students,
    is_user_exists, ensure_user_with_post, set_user_name,
    list_local_admins  # список всех ЛА (с привязкой к школам)
)
# ✨ Новая утилита — список ГА
from db import list_global_admins

from config import DB_PATH

# Примитивное FSM для различных сценариев
GA_STATE: dict[int, dict] = {}

# FSM для активации приглашения ЛА — теперь здесь
COMMON_STATE: dict[int, dict] = {}

class IsGaOrCommonInput(BaseFilter):
    async def __call__(self, msg: Message) -> bool:
        uid = msg.from_user.id
        st_common = COMMON_STATE.get(uid)
        if st_common and st_common.get("mode") == "await_la_password":
            return True
        st_ga = GA_STATE.get(uid)
        return bool(st_ga)


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


# --- Редактирование локальных администраторов ---
@router.callback_query(F.data == CB_GA_EDIT_LA)
async def ga_edit_la_start(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_global_admin(cq.from_user.id):
        return

    schools = await list_schools()
    if not schools:
        return await cq.message.edit_text(
            "❌ Нет учебных заведений.",
            reply_markup=ga_core_kb()
        )

    rows = [(f"{s['name']}", f"ga_edit_la_pick:{s['id']}") for s in schools]
    rows.append(("⬅️ Назад в «Основные»", CB_GA_BACK_TO_CORE))
    await cq.message.edit_text(
        "Выберите учебное заведение, чьих локальных администраторов вы хотите редактировать:",
        reply_markup=single_col_kb(rows)
    )


@router.callback_query(F.data.startswith("ga_edit_la_pick:"))
async def ga_edit_la_pick_school(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)

    try:
        school_id = int(cq.data.split(":", 1)[1])
    except ValueError:
        return await cq.answer("Некорректный ID школы", show_alert=True)

    school = await get_school_by_id(school_id)
    if not school:
        return await cq.answer("УЗ не найдено", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT user_id FROM school_local_admins WHERE school_id = ?", (school_id,)
        )
        la_list = await cur.fetchall()

    if not la_list:
        return await cq.message.edit_text(
            f"В <b>{school['name']}</b> пока нет локальных администраторов.",
            reply_markup=back_to_core_kb()
        )

    la_ids = [str(r["user_id"]) for r in la_list]
    la_text = "\n".join([f"• <code>{uid}</code>" for uid in la_ids])
    buttons = [
        [InlineKeyboardButton(text=f"Удалить ЛА {uid}", callback_data=f"ga_remove_la:{school_id}:{uid}")]
        for uid in la_ids
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в «Основные»", callback_data=CB_GA_BACK_TO_CORE)])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await cq.message.edit_text(
        f"Локальные администраторы в <b>{school['name']}</b>:\n\n{la_text}\n\n"
        f"Выберите ЛА, роль которого хотите отозвать:",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("ga_remove_la:"))
async def ga_remove_la(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)

    try:
        _, school_id, user_id = cq.data.split(":", 2)
        school_id = int(school_id)
        user_id = int(user_id)
    except ValueError:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Проверка
        cur = await db.execute(
            "SELECT 1 FROM school_local_admins WHERE school_id = ? AND user_id = ?",
            (school_id, user_id)
        )
        row = await cur.fetchone()
        if not row:
            return await cq.answer("❌ Этот пользователь не является ЛА в этой школе.", show_alert=True)

        # Удаление
        await db.execute("DELETE FROM school_local_admins WHERE school_id = ? AND user_id = ?", (school_id, user_id))
        await db.commit()

        # Проверяем, остались ли у пользователя роли
        cur = await db.execute("SELECT 1 FROM school_local_admins WHERE user_id = ? LIMIT 1", (user_id,))
        r_la = await cur.fetchone()
        cur = await db.execute("SELECT 1 FROM school_teachers WHERE user_id = ? LIMIT 1", (user_id,))
        r_t = await cur.fetchone()
        cur = await db.execute("SELECT 1 FROM school_students WHERE user_id = ? LIMIT 1", (user_id,))
        r_s = await cur.fetchone()
        cur = await db.execute("SELECT 1 FROM administrators WHERE AdminID = ? LIMIT 1", (user_id,))
        r_ga = await cur.fetchone()

        if not any([r_la, r_t, r_s, r_ga]):
            await db.execute("DELETE FROM users WHERE UserID = ?", (user_id,))
            await db.commit()

    await cq.answer("✅ Роль локального администратора отозвана.", show_alert=True)
    await ga_edit_la_pick_school(cq)


# --- Обработка текстовых сообщений (все FSM) ---
@router.message(F.text, IsGaOrCommonInput())
async def handle_ga_text_input(msg: Message):
    user_id = msg.from_user.id

    st_common = COMMON_STATE.get(user_id)
    if st_common and st_common.get("mode") == "await_la_password":
        await _handle_la_password_input(msg, st_common)
        return

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
    elif mode == "ga_assign_teacher":
        await _handle_ga_assign_teacher_step(msg, st)
    elif mode == "ga_assign_student":
        await _handle_ga_assign_student_step(msg, st)
    elif mode == "ga_rename_teacher":
        await _handle_ga_rename_teacher_step(msg, st)
    elif mode == "ga_rename_student":
        await _handle_ga_rename_student_step(msg, st)
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

    invite_link = f"https://t.me/{bot_username}?start={password}"

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


# ---------------------------------------------------------------------------
#                 «ДОПОЛНИТЕЛЬНЫЕ/ИНФО»: Учителя/Ученики/Списки
# ---------------------------------------------------------------------------

# === Назначить учителя ===
@router.callback_query(F.data == CB_GA_ASSIGN_TEACHER)
async def ga_assign_teacher_start(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_global_admin(cq.from_user.id):
        return
    schools = await list_schools()
    if not schools:
        return await cq.message.edit_text(
            "❌ Нет учебных заведений. Сначала создайте хотя бы одно.",
            reply_markup=ga_core_kb()
        )
    rows = [(s["name"], f"ga_assign_teacher_pick:{s['id']}") for s in schools]
    rows.append(("⬅️ Назад в «Дополнительные»", CB_GA_SEC_MORE))
    await cq.message.edit_text("Выберите учебное заведение:", reply_markup=single_col_kb(rows))

@router.callback_query(F.data.startswith("ga_assign_teacher_pick:"))
async def ga_assign_teacher_pick_school(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        school_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    school = await get_school_by_id(school_id)
    if not school:
        return await cq.answer("УЗ не найдено", show_alert=True)
    GA_STATE[cq.from_user.id] = {
        "mode": "ga_assign_teacher",
        "school_id": school_id,
        "school_name": school["name"],
    }
    await cq.message.edit_text(
        f"👩‍🏫 Назначение учителя в <b>{school['name']}</b>\n\n"
        f"Отправьте <b>Telegram ID</b> пользователя (только цифры).",
        reply_markup=back_kb()
    )

async def _handle_ga_assign_teacher_step(msg: Message, st: dict):
    raw = msg.text.strip()
    if not raw.isdigit():
        return await msg.answer("❌ Некорректный Telegram ID. Отправьте только цифры.", reply_markup=back_kb())
    user_id = int(raw)
    school_id = st["school_id"]
    school_name = st["school_name"]

    await ensure_user_with_post(user_id, post="teacher")
    await assign_teacher_to_school(school_id, user_id)

    GA_STATE.pop(msg.from_user.id, None)
    await msg.answer(
        f"✅ Учитель <code>{user_id}</code> назначен в школу <b>{school_name}</b>.",
        reply_markup=ga_more_kb()
    )


# === Назначить ученика ===
@router.callback_query(F.data == CB_GA_ASSIGN_STUDENT)
async def ga_assign_student_start(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq) or not await is_global_admin(cq.from_user.id):
        return
    schools = await list_schools()
    if not schools:
        return await cq.message.edit_text(
            "❌ Нет учебных заведений. Сначала создайте хотя бы одно.",
            reply_markup=ga_core_kb()
        )
    rows = [(s["name"], f"ga_assign_student_pick:{s['id']}") for s in schools]
    rows.append(("⬅️ Назад в «Дополнительные»", CB_GA_SEC_MORE))
    await cq.message.edit_text("Выберите учебное заведение:", reply_markup=single_col_kb(rows))

@router.callback_query(F.data.startswith("ga_assign_student_pick:"))
async def ga_assign_student_pick_school(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return await cq.answer("Недостаточно прав", show_alert=True)
    try:
        school_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    school = await get_school_by_id(school_id)
    if not school:
        return await cq.answer("УЗ не найдено", show_alert=True)
    GA_STATE[cq.from_user.id] = {
        "mode": "ga_assign_student",
        "school_id": school_id,
        "school_name": school["name"],
    }
    await cq.message.edit_text(
        f"👨‍🎓 Назначение ученика в <b>{school['name']}</b>\n\n"
        f"Отправьте <b>Telegram ID</b> пользователя (только цифры).",
        reply_markup=back_kb()
    )

async def _handle_ga_assign_student_step(msg: Message, st: dict):
    raw = msg.text.strip()
    if not raw.isdigit():
        return await msg.answer("❌ Некорректный Telegram ID. Отправьте только цифры.", reply_markup=back_kb())
    user_id = int(raw)
    school_id = st["school_id"]
    school_name = st["school_name"]

    await ensure_user_with_post(user_id, post="student")
    await assign_student_to_school(school_id, user_id)

    GA_STATE.pop(msg.from_user.id, None)
    await msg.answer(
        f"✅ Ученик <code>{user_id}</code> добавлен в школу <b>{school_name}</b>.",
        reply_markup=ga_more_kb()
    )


# === Редактировать учителей ===
@router.callback_query(F.data == CB_GA_EDIT_TEACHERS)
async def ga_edit_teachers(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    schools = await list_schools()
    if not schools:
        return await cq.message.edit_text("❌ Нет учебных заведений.", reply_markup=ga_core_kb())
    rows = [(s["name"], f"ga_edit_teachers_pick:{s['id']}") for s in schools]
    rows.append(("⬅️ Назад в «Дополнительные»", CB_GA_SEC_MORE))
    await cq.message.edit_text("Выберите учебное заведение:", reply_markup=single_col_kb(rows))

@router.callback_query(F.data.startswith("ga_edit_teachers_pick:"))
async def ga_edit_teachers_pick(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    try:
        school_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    teachers = await list_school_teachers(school_id)
    if not teachers:
        return await cq.message.edit_text("В этой школе ещё нет учителей.", reply_markup=ga_more_kb())
    rows = [(f"{t['name']} (ID {t['user_id']})", f"ga_edit_teacher_actions:{school_id}:{t['user_id']}") for t in teachers]
    rows.append(("⬅️ Назад", CB_GA_EDIT_TEACHERS))
    await cq.message.edit_text("Выберите учителя:", reply_markup=single_col_kb(rows))

@router.callback_query(F.data.startswith("ga_edit_teacher_actions:"))
async def ga_edit_teacher_actions(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    try:
        _, school_id, user_id = cq.data.split(":")
        school_id = int(school_id); user_id = int(user_id)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"ga_rename_teacher:{school_id}:{user_id}")],
        [InlineKeyboardButton(text="🗑 Удалить из школы", callback_data=f"ga_remove_teacher:{school_id}:{user_id}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data=f"ga_edit_teachers_pick:{school_id}")]
    ])
    await cq.message.edit_text(f"Учитель ID <code>{user_id}</code>. Выберите действие:", reply_markup=kb)

@router.callback_query(F.data.startswith("ga_remove_teacher:"))
async def ga_remove_teacher(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    try:
        _, school_id, user_id = cq.data.split(":")
        school_id = int(school_id); user_id = int(user_id)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    await remove_teacher_from_school(school_id, user_id)
    await cq.answer("Удалено.")
    await ga_edit_teachers_pick(cq)

@router.callback_query(F.data.startswith("ga_rename_teacher:"))
async def ga_rename_teacher(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    try:
        _, school_id, user_id = cq.data.split(":")
        school_id = int(school_id); user_id = int(user_id)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    GA_STATE[cq.from_user.id] = {"mode": "ga_rename_teacher", "school_id": school_id, "user_id": user_id}
    await cq.message.edit_text("Введите новое имя учителя:", reply_markup=back_kb())

async def _handle_ga_rename_teacher_step(msg: Message, st: dict):
    name = msg.text.strip()
    user_id = st["user_id"]
    await set_user_name(user_id, name)
    GA_STATE.pop(msg.from_user.id, None)
    await msg.answer("Имя учителя обновлено.", reply_markup=ga_more_kb())


# === Редактировать учеников ===
@router.callback_query(F.data == CB_GA_EDIT_STUDENTS)
async def ga_edit_students(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    schools = await list_schools()
    if not schools:
        return await cq.message.edit_text("❌ Нет учебных заведений.", reply_markup=ga_core_kb())
    rows = [(s["name"], f"ga_edit_students_pick:{s['id']}") for s in schools]
    rows.append(("⬅️ Назад в «Дополнительные»", CB_GA_SEC_MORE))
    await cq.message.edit_text("Выберите учебное заведение:", reply_markup=single_col_kb(rows))

@router.callback_query(F.data.startswith("ga_edit_students_pick:"))
async def ga_edit_students_pick(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    try:
        school_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    students = await list_school_students(school_id)
    if not students:
        return await cq.message.edit_text("В этой школе ещё нет учеников.", reply_markup=ga_more_kb())
    rows = [(f"{s['name']} (ID {s['user_id']})", f"ga_edit_student_actions:{school_id}:{s['user_id']}") for s in students]
    rows.append(("⬅️ Назад", CB_GA_EDIT_STUDENTS))
    await cq.message.edit_text("Выберите ученика:", reply_markup=single_col_kb(rows))

@router.callback_query(F.data.startswith("ga_edit_student_actions:"))
async def ga_edit_student_actions(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    try:
        _, school_id, user_id = cq.data.split(":")
        school_id = int(school_id); user_id = int(user_id)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"ga_rename_student:{school_id}:{user_id}")],
        [InlineKeyboardButton(text="🗑 Удалить из школы", callback_data=f"ga_remove_student:{school_id}:{user_id}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data=f"ga_edit_students_pick:{school_id}")]
    ])
    await cq.message.edit_text(f"Ученик ID <code>{user_id}</code>. Выберите действие:", reply_markup=kb)

@router.callback_query(F.data.startswith("ga_remove_student:"))
async def ga_remove_student(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    try:
        _, school_id, user_id = cq.data.split(":")
        school_id = int(school_id); user_id = int(user_id)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    await remove_student_from_school(school_id, user_id)
    await cq.answer("Удалено.")
    await ga_edit_students_pick(cq)

@router.callback_query(F.data.startswith("ga_rename_student:"))
async def ga_rename_student(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    try:
        _, school_id, user_id = cq.data.split(":")
        school_id = int(school_id); user_id = int(user_id)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    GA_STATE[cq.from_user.id] = {"mode": "ga_rename_student", "school_id": school_id, "user_id": user_id}
    await cq.message.edit_text("Введите новое имя ученика:", reply_markup=back_kb())

async def _handle_ga_rename_student_step(msg: Message, st: dict):
    name = msg.text.strip()
    user_id = st["user_id"]
    await set_user_name(user_id, name)
    GA_STATE.pop(msg.from_user.id, None)
    await msg.answer("Имя ученика обновлено.", reply_markup=ga_more_kb())


# === Информационные разделы: списки учителей/учеников ===
@router.callback_query(F.data == CB_GA_LIST_TEACHERS)
async def ga_list_teachers(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    schools = await list_schools()
    if not schools:
        return await cq.answer("Нет УЗ.", show_alert=True)
    if len(schools) == 1:
        school_id = schools[0]["id"]; school_name = schools[0]["name"]
        teachers = await list_school_teachers(school_id)
        if not teachers:
            return await cq.message.edit_text(f"В <b>{school_name}</b> учителей пока нет.", reply_markup=ga_info_kb())
        text = f"👩‍🏫 <b>Учителя</b> — {school_name}\n\n"
        for t in teachers:
            text += f"• {t['name']} (ID {t['user_id']})\n"
        return await cq.message.edit_text(text, reply_markup=ga_info_kb())
    rows = [(s["name"], f"ga_list_teachers_pick:{s['id']}") for s in schools]
    rows.append(("⬅ Назад", CB_GA_SEC_INFO))
    await cq.message.edit_text("Выберите УЗ:", reply_markup=single_col_kb(rows))

@router.callback_query(F.data.startswith("ga_list_teachers_pick:"))
async def ga_list_teachers_pick(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    try:
        school_id = int(cq.data.split(':',1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    school = await get_school_by_id(school_id)
    teachers = await list_school_teachers(school_id)
    name = school["name"] if school else f"ID {school_id}"
    if not teachers:
        return await cq.message.edit_text(f"В <b>{name}</b> учителей пока нет.", reply_markup=ga_info_kb())
    text = f"👩‍🏫 <b>Учителя</b> — {name}\n\n"
    for t in teachers:
        text += f"• {t['name']} (ID {t['user_id']})\n"
    await cq.message.edit_text(text, reply_markup=ga_info_kb())

@router.callback_query(F.data == CB_GA_LIST_STUDENTS)
async def ga_list_students(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    schools = await list_schools()
    if not schools:
        return await cq.answer("Нет УЗ.", show_alert=True)
    if len(schools) == 1:
        school_id = schools[0]["id"]; school_name = schools[0]["name"]
        students = await list_school_students(school_id)
        if not students:
            return await cq.message.edit_text(f"В <b>{school_name}</b> учеников пока нет.", reply_markup=ga_info_kb())
        text = f"👨‍🎓 <b>Ученики</b> — {school_name}\n\n"
        for s in students:
            text += f"• {s['name']} (ID {s['user_id']})\n"
        return await cq.message.edit_text(text, reply_markup=ga_info_kb())
    rows = [(s["name"], f"ga_list_students_pick:{s['id']}") for s in schools]
    rows.append(("⬅ Назад", CB_GA_SEC_INFO))
    await cq.message.edit_text("Выберите УЗ:", reply_markup=single_col_kb(rows))

@router.callback_query(F.data.startswith("ga_list_students_pick:"))
async def ga_list_students_pick(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    try:
        school_id = int(cq.data.split(':',1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)
    school = await get_school_by_id(school_id)
    students = await list_school_students(school_id)
    name = school["name"] if school else f"ID {school_id}"
    if not students:
        return await cq.message.edit_text(f"В <b>{name}</b> учеников пока нет.", reply_markup=ga_info_kb())
    text = f"👨‍🎓 <b>Ученики</b> — {name}\n\n"
    for s in students:
        text += f"• {s['name']} (ID {s['user_id']})\n"
    await cq.message.edit_text(text, reply_markup=ga_info_kb())


# === НОВОЕ: Информационные — Список УЗ / Список ЛА / Список ГА ===
@router.callback_query(F.data == CB_GA_LIST_SCHOOLS)
async def ga_list_schools_info(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    schools = await list_schools()
    if not schools:
        return await cq.message.edit_text("🏫 Учебных заведений пока нет.", reply_markup=ga_info_kb())
    lines = []
    for s in schools:
        short = s.get("short_name") or "—"
        tz = s.get("timezone") or "UTC"
        lines.append(f"• <b>{s['name']}</b> (ID {s['id']}, кратко: {short}, TZ: {tz})")
    await cq.message.edit_text("🏫 <b>Учебные заведения</b>\n\n" + "\n".join(lines), reply_markup=ga_info_kb())


@router.callback_query(F.data == CB_GA_LIST_LA)
async def ga_list_local_admins_info(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    rows = await list_local_admins()
    if not rows:
        return await cq.message.edit_text("👤 Локальные администраторы не найдены.", reply_markup=ga_info_kb())

    # Группируем по школе
    grouped: dict[str, list[str]] = {}
    for r in rows:
        school_name = r.get("school_name") or f"Школа ID {r.get('school_id')}"
        user_id = r.get("UserID") or r.get("user_id")
        name = r.get("name") or "Без имени"
        grouped.setdefault(school_name, []).append(f"• {name} (ID {user_id})")

    parts = []
    for school, items in grouped.items():
        parts.append(f"🏫 <b>{school}</b>\n" + "\n".join(items))
    await cq.message.edit_text("👥 <b>Локальные администраторы</b>\n\n" + "\n\n".join(parts), reply_markup=ga_info_kb())


@router.callback_query(F.data == CB_GA_LIST_GA)
async def ga_list_global_admins_info(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id):
        return
    rows = await list_global_admins()
    if not rows:
        return await cq.message.edit_text("🛡 Глобальные администраторы отсутствуют.", reply_markup=ga_info_kb())
    text = "🛡 <b>Глобальные администраторы</b>\n\n" + "\n".join(
        f"• {r['name']} (ID {r['user_id']})" for r in rows
    )
    await cq.message.edit_text(text, reply_markup=ga_info_kb())
