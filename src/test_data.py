# seed_test_data.py
import asyncio
from datetime import datetime, timezone

import aiosqlite

from config import DB_PATH
from db import (
    ensure_db,
    ensure_user_with_post,
    assign_teacher_to_school,
    assign_student_to_school,
)

# ⬇⬇⬇ ОБЯЗАТЕЛЬНО ПОДСТАВЬ СВОЙ Telegram ID
LOCAL_ADMIN_ID = 5234268303   # <= ЗАМЕНИ на свой реальный Telegram ID!
GLOBAL_ADMIN_ID = 987654321  # можешь тоже заменить на свой или другой тестовый ID

# Просто тестовые ID для “фейковых” учителей и учеников
TEACHER1_ID = 651213276
TEACHER2_ID = 20002
STUDENT1_ID = 30001
STUDENT2_ID = 30002


async def seed():
    # Создаём таблицы, если их ещё нет
    await ensure_db()

    now = datetime.now(timezone.utc).isoformat()

    # 1) Школы, локальный админ, классы, глобальный админ
    async with aiosqlite.connect(DB_PATH) as db:
        # чтобы SELECT возвращал dict-подобные строки, если понадобится
        db.row_factory = aiosqlite.Row

        # --- ШКОЛЫ ---
        await db.execute(
            """
            INSERT OR IGNORE INTO schools(id, name, short_name, address, timezone, created_utc, updated_utc)
            VALUES (1, 'Тестовая школа №1', 'Шк№1', 'Город, улица 1', 'UTC', ?, ?)
            """,
            (now, now),
        )
        await db.execute(
            """
            INSERT OR IGNORE INTO schools(id, name, short_name, address, timezone, created_utc, updated_utc)
            VALUES (2, 'Тестовая школа №2', 'Шк№2', 'Город, улица 2', 'UTC', ?, ?)
            """,
            (now, now),
        )

        # --- ЛОКАЛЬНЫЙ АДМИН ПРИВЯЗАН К ОБЕИМ ШКОЛАМ ---
        await db.execute(
            "INSERT OR IGNORE INTO school_local_admins(school_id, user_id) VALUES (1, ?)",
            (LOCAL_ADMIN_ID,),
        )
        await db.execute(
            "INSERT OR IGNORE INTO school_local_admins(school_id, user_id) VALUES (2, ?)",
            (LOCAL_ADMIN_ID,),
        )

        # --- КЛАССЫ (для мастера добавления ученика) ---
        # владелец класса не критичен для ЛА, но пусть будет какой-то ID
        await db.execute(
            "INSERT OR IGNORE INTO classes(id, name, owner_chat_id) VALUES (1, '5А', ?)",
            (TEACHER1_ID,),
        )
        await db.execute(
            "INSERT OR IGNORE INTO classes(id, name, owner_chat_id) VALUES (2, '6Б', ?)",
            (TEACHER2_ID,),
        )

        # --- ГЛОБАЛЬНЫЙ АДМИН ---
        await db.execute(
            "INSERT OR IGNORE INTO administrators(AdminID) VALUES (?)",
            (GLOBAL_ADMIN_ID,),
        )

        await db.commit()

    # 2) Пользователи и их роли (users.post)

    # Локальный админ
    await ensure_user_with_post(
        LOCAL_ADMIN_ID,
        post="local_admin",
        name="ЛА Тестовый",
    )

    # Учителя
    await ensure_user_with_post(
        TEACHER1_ID,
        post="teacher",
        name="Учитель Петров",
    )
    await ensure_user_with_post(
        TEACHER2_ID,
        post="teacher",
        name="Учитель Смирнов",
    )

    # Ученики
    await ensure_user_with_post(
        STUDENT1_ID,
        post="student",
        name="Ученик Иванов",
    )
    await ensure_user_with_post(
        STUDENT2_ID,
        post="student",
        name="Ученик Сидоров",
    )

    # 3) Привязки учителей и учеников к школам

    # Учителя по школам
    await assign_teacher_to_school(1, TEACHER1_ID)
    await assign_teacher_to_school(1, TEACHER2_ID)
    await assign_teacher_to_school(2, TEACHER2_ID)

    # Ученики по школам
    await assign_student_to_school(1, STUDENT1_ID)
    await assign_student_to_school(2, STUDENT2_ID)

    print("✅ Тестовые данные успешно записаны в БД:", DB_PATH)


if __name__ == "__main__":
    asyncio.run(seed())
