# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import CallbackQuery
import aiosqlite

from config import DB_PATH
from db import fetchall, fetchone
from keyboards import back_kb, single_col_kb
from callbacks import (
    CB_ENROLL, CB_ENROLL_PICK_STU, CB_ENROLL_PICK_CLS, CB_STU_AFTER_ADD_SKIP
)
from utils import display_student

router = Router()

@router.callback_query(F.data == CB_ENROLL)
async def cb_enroll(cq: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        students = await fetchall(db, "SELECT id, name, username FROM students ORDER BY name COLLATE NOCASE ASC")
    if not students:
        return await cq.message.edit_text("Пока нет учеников.", reply_markup=back_kb())
    rows = [(display_student(s["name"], s["username"]), f"{CB_ENROLL_PICK_STU}{s['id']}") for s in students]
    await cq.message.edit_text("🔗 <b>Выберите ученика</b>:", reply_markup=single_col_kb(rows))

@router.callback_query(F.data.startswith(CB_ENROLL_PICK_STU))
async def cb_enroll_pick_student(cq: CallbackQuery):
    try:
        student_id = int(cq.data.split(":", 1)[1])
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        s = await fetchone(db, "SELECT name, username FROM students WHERE id=?", (student_id,))
        classes = await fetchall(db, "SELECT id, name FROM classes ORDER BY name COLLATE NOCASE ASC")
    if not s:
        return await cq.answer("Ученик не найден", show_alert=True)
    if not classes:
        return await cq.message.edit_text("Пока нет классов. Сначала создайте класс.", reply_markup=back_kb())

    student_title = display_student(s["name"], s["username"])
    rows = [(c['name'], f"{CB_ENROLL_PICK_CLS}{student_id}:{c['id']}") for c in classes]
    rows.append(("⏭ Пропустить", CB_STU_AFTER_ADD_SKIP))
    await cq.message.edit_text(
        f"🔗 Ученик: <b>{student_title}</b>\n\nВыберите <b>класс</b>:",
        reply_markup=single_col_kb(rows)
    )

@router.callback_query(F.data.startswith(CB_ENROLL_PICK_CLS))
async def cb_enroll_pick_class(cq: CallbackQuery):
    try:
        _, payload = cq.data.split(":", 1)
        student_id_str, class_id_str = payload.split(":")
        student_id = int(student_id_str)
        class_id = int(class_id_str)
    except Exception:
        return await cq.answer("Некорректные данные", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        s = await fetchone(db, "SELECT name, username FROM students WHERE id=?", (student_id,))
        c = await fetchone(db, "SELECT name FROM classes WHERE id=?", (class_id,))

        if not s or not c:
            return await cq.answer("Ученик или класс не найден", show_alert=True)

        try:
            await db.execute("INSERT OR IGNORE INTO enrollments(student_id, class_id) VALUES(?, ?)", (student_id, class_id))
            await db.commit()
        except Exception as e:
            return await cq.message.edit_text(f"Ошибка: {e}", reply_markup=back_kb())

    await cq.message.edit_text(
        f"✅ Привязка выполнена:\n"
        f"Ученик: <b>{display_student(s['name'], s['username'])}</b>\n"
        f"Класс: <b>{c['name']}</b>",
        reply_markup=back_kb()
    )
