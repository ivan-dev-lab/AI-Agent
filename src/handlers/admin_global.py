from aiogram import Router, F
from aiogram.types import CallbackQuery
from utils import ensure_authorized, is_global_admin
from keyboards import ga_panel_kb, ga_core_kb, ga_more_kb, ga_info_kb
from callbacks import (
    CB_GA_MENU, CB_GA_SEC_CORE, CB_GA_SEC_MORE, CB_GA_SEC_INFO,
    CB_GA_ADD_SCHOOL, CB_GA_EDIT_SCHOOLS, CB_GA_ASSIGN_LA, CB_GA_EDIT_LA,
    CB_GA_ASSIGN_TEACHER, CB_GA_ASSIGN_STUDENT, CB_GA_EDIT_TEACHERS, CB_GA_EDIT_STUDENTS,
    CB_GA_LIST_SCHOOLS, CB_GA_LIST_LA, CB_GA_LIST_TEACHERS, CB_GA_LIST_STUDENTS, CB_GA_LIST_GA,
)

router = Router()

# --- вход в панель разделов ---
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

# --- открытие разделов ---
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

# --- заглушки для действий (пока без реализации) ---
@router.callback_query(F.data == CB_GA_ADD_SCHOOL)
async def ga_add_school(cq: CallbackQuery):
    if not await is_global_admin(cq.from_user.id): return
    await cq.answer("Добавление УЗ — скоро ✨", show_alert=True)

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
