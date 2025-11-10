# src/handlers/teacher.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
import aiosqlite

from utils import ensure_authorized, has_post
from keyboards import back_kb, teacher_main_kb
from callbacks import (
    CB_T_ASSIGN_STUDENT, CB_T_EDIT_STUDENTS, CB_T_CREATE_GROUP,
    CB_T_EDIT_GROUP, CB_T_ADD_TASK, CB_T_LIST_TASKS, CB_BACK
)

router = Router()

# Показываем меню (если захотите показывать через callback CB_TEACHER_MENU)
@router.callback_query(F.data == CB_BACK)  # back уже маршрутизируется в common, но оставим на случай
async def cb_t_back(cq: CallbackQuery):
    # Перенаправление на общий back_to_main уже реализовано в common
    # Эта заглушка просто закроет клавиатуру если нужно
    await cq.answer()

@router.callback_query(F.data == CB_T_ASSIGN_STUDENT)
async def cb_t_assign_student(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    await cq.message.edit_text("👨‍🎓 <b>Назначить ученика</b>\n\nВведите /assign_student <telegram_id> или воспользуйтесь будущим интерфейсом.", reply_markup=back_kb())

@router.callback_query(F.data == CB_T_EDIT_STUDENTS)
async def cb_t_edit_students(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    await cq.message.edit_text("✏️ <b>Редактировать учеников</b>\n\nЗдесь позже появится интерфейс редактирования.", reply_markup=back_kb())

@router.callback_query(F.data == CB_T_CREATE_GROUP)
async def cb_t_create_group(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    await cq.message.edit_text("📁 <b>Создать группу</b>\n\nИспользование: /add_class <имя_группы>", reply_markup=back_kb())

@router.callback_query(F.data == CB_T_EDIT_GROUP)
async def cb_t_edit_group(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    await cq.message.edit_text("⚙️ <b>Редактировать группу</b>\n\nЗдесь появится интерфейс для добавления/удаления учеников из группы.", reply_markup=back_kb())

@router.callback_query(F.data == CB_T_ADD_TASK)
async def cb_t_add_task(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    # переиспользуем существующий обработчик добавления задания, если он есть;
    # пока — заглушка:
    await cq.message.edit_text("➕ <b>Добавить задание</b>\n\nВведите /add_task <текст задания>", reply_markup=back_kb())

@router.callback_query(F.data == CB_T_LIST_TASKS)
async def cb_t_list_tasks(cq: CallbackQuery):
    if not await ensure_authorized(cq.from_user.id, cq):
        return
    if not await has_post(cq.from_user.id, "teacher"):
        return await cq.answer("Недостаточно прав", show_alert=True)
    await cq.message.edit_text("📋 <b>Список заданий</b>\n\nЗдесь будет список заданий для вашего класса.", reply_markup=back_kb())
