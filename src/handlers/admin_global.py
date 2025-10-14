from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from zoneinfo import ZoneInfo

from utils import ensure_authorized, is_global_admin
from keyboards import ga_panel_kb, ga_core_kb, ga_more_kb, ga_info_kb, back_kb
from callbacks import (
    CB_GA_MENU, CB_GA_SEC_CORE, CB_GA_SEC_MORE, CB_GA_SEC_INFO,
    CB_GA_ADD_SCHOOL, CB_GA_EDIT_SCHOOLS, CB_GA_ASSIGN_LA, CB_GA_EDIT_LA,
    CB_GA_ASSIGN_TEACHER, CB_GA_ASSIGN_STUDENT, CB_GA_EDIT_TEACHERS, CB_GA_EDIT_STUDENTS,
    CB_GA_LIST_SCHOOLS, CB_GA_LIST_LA, CB_GA_LIST_TEACHERS, CB_GA_LIST_STUDENTS, CB_GA_LIST_GA,
)
from callbacks import (
    CB_GA_EDIT_SCHOOLS, CB_GA_ED_S_PICK,
    CB_GA_ED_S_NAME, CB_GA_ED_S_SHORT, CB_GA_ED_S_ADDR, CB_GA_ED_S_TZ
)
from keyboards import single_col_kb, ga_edit_school_detail_kb
from db import list_schools, get_school_by_id, update_school_field

from db import create_school

router = Router()

# Примитивное FSM для добавления УЗ (в памяти)
# GA_STATE[user_id] = {"mode": "ga_add_school", "step": 0..3, "data": {...}}
GA_STATE: dict[int, dict] = {}

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

# --- Заглушки других пунктов (пока без реализации) ---
@router.callback_query(F.data == CB_GA_EDIT_SCHOOLS)
async def ga_edit_schools(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Редактирование УЗ — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_ASSIGN_LA)
async def ga_assign_la(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Назначение ЛА — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_EDIT_LA)
async def ga_edit_la(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Редактирование ЛА — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_ASSIGN_TEACHER)
async def ga_assign_teacher(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Назначить учителя — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_ASSIGN_STUDENT)
async def ga_assign_student(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Назначить ученика — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_EDIT_TEACHERS)
async def ga_edit_teachers(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Редактирование учителей — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_EDIT_STUDENTS)
async def ga_edit_students(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Редактирование учеников — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_LIST_SCHOOLS)
async def ga_list_schools(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Список УЗ — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_LIST_LA)
async def ga_list_la(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Список ЛА — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_LIST_TEACHERS)
async def ga_list_teachers(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Список учителей — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_LIST_STUDENTS)
async def ga_list_students(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Список учеников — скоро ✨", show_alert=True)

@router.callback_query(F.data == CB_GA_LIST_GA)
async def ga_list_ga(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Список глобальных админов — скоро ✨", show_alert=True)

# --- Обработка шагов мастера "Добавить УЗ" ---
@router.message(F.text)
async def ga_add_school_steps(msg: Message):
    st = GA_STATE.get(msg.from_user.id)
    if not st or st.get("mode") != "ga_add_school":
        # не наш мастер — пропускаем в другие роутеры
        return

    # проверка прав
    # (если за время мастера права изменились/пользователь не авторизован)
    from utils import ensure_authorized as _ensure, is_global_admin as _is_ga
    if not await _ensure(msg.from_user.id, msg) or not await _is_ga(msg.from_user.id):
        GA_STATE.pop(msg.from_user.id, None)
        return

    step = st.get("step", 0)
    data = st.setdefault("data", {})

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
        # валидация таймзоны (мягкая)
        try:
            _ = ZoneInfo(tz)
        except Exception:
            tz = "UTC"

        # запись в БД
        try:
            school_id = await create_school(
                name=data["name"],
                short_name=data.get("short_name"),
                address=data.get("address"),
                tz=tz
            )
        except Exception as e:
            GA_STATE.pop(msg.from_user.id, None)
            return await msg.answer(f"❌ Ошибка создания УЗ: {e}", reply_markup=ga_core_kb())

        GA_STATE.pop(msg.from_user.id, None)
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

def _format_school_card(s: dict) -> str:
    return (
        "🏫 <b>Учебное заведение</b>\n\n"
        f"ID: <code>{s['id']}</code>\n"
        f"Название: <b>{s['name']}</b>\n"
        f"Краткое имя: <b>{s.get('short_name') or '—'}</b>\n"
        f"Адрес: <b>{s.get('address') or '—'}</b>\n"
        f"Таймзона: <code>{s.get('timezone') or 'UTC'}</code>"
    )

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
                            "Введите <b>IANA таймзону</b> (например, <code>Europe/Moscow</code>)\n"
                            "Или «-» для <code>UTC</code>.")
    await cq.message.edit_text(txt, reply_markup=ga_edit_school_detail_kb(sid))

from zoneinfo import ZoneInfo

@router.message(F.text)
async def ga_edit_school_text(msg: Message):
    st = GA_STATE.get(msg.from_user.id)
    if not st or st.get("mode") != "ga_edit_school":
        return  # не наш сценарий

    if not await ensure_authorized(msg.from_user.id, msg) or not await is_global_admin(msg.from_user.id):
        GA_STATE.pop(msg.from_user.id, None)
        return

    school_id = st["school_id"]
    field = st["field"]
    raw = msg.text.strip()

    # Нормализация значений
    value = raw
    if field in ("short_name", "address") and raw == "-":
        value = None
    if field == "timezone":
        value = "UTC" if raw == "-" else raw
        try:
            _ = ZoneInfo(value)
        except Exception:
            return await msg.answer("❌ Некорректная таймзона. Пример: <code>Europe/Moscow</code> или «-».")
    if field == "name" and len(raw) < 2:
        return await msg.answer("❌ Название слишком короткое.")

    # Обновление в БД
    try:
        await update_school_field(school_id, field, value)
    except Exception as e:
        GA_STATE.pop(msg.from_user.id, None)
        return await msg.answer(f"❌ Ошибка сохранения: {e}")

    # Показать обновлённую карточку
    s = await get_school_by_id(school_id)
    GA_STATE.pop(msg.from_user.id, None)
    if not s:
        return await msg.answer("⚠️ УЗ не найдено после обновления (удалено?)")
    await msg.answer("✅ Изменения сохранены.")
    await msg.answer(_format_school_card(s), reply_markup=ga_edit_school_detail_kb(school_id))
