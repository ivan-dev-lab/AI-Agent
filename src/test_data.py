# seed_test_data.py
import asyncio
from datetime import datetime

import aiosqlite

from config import DB_PATH, DEFAULT_TZ, DEFAULT_TZINFO
from db import (
    ensure_db,
    ensure_user_with_post,
    assign_teacher_to_school,
    assign_student_to_school,
)

# Demo user ids — replace with your own when needed
LOCAL_ADMIN_ID = 5234268303
TEACHER1_ID = 651213276
TEACHER2_ID = 20002
STUDENT1_ID = 30001
STUDENT2_ID = 30002


async def seed() -> None:
    await ensure_db()

    now = datetime.now(DEFAULT_TZINFO).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        await db.execute(
            """
            INSERT OR IGNORE INTO schools(id, name, short_name, address, timezone, created_utc, updated_utc)
            VALUES (1, 'School-1', 'Sch1', 'Address 1', ?, ?, ?)
            """,
            (DEFAULT_TZ, now, now),
        )
        await db.execute(
            """
            INSERT OR IGNORE INTO schools(id, name, short_name, address, timezone, created_utc, updated_utc)
            VALUES (2, 'School-2', 'Sch2', 'Address 2', ?, ?, ?)
            """,
            (DEFAULT_TZ, now, now),
        )

        await db.execute(
            "INSERT OR IGNORE INTO school_local_admins(school_id, user_id) VALUES (1, ?)",
            (LOCAL_ADMIN_ID,),
        )
        await db.execute(
            "INSERT OR IGNORE INTO school_local_admins(school_id, user_id) VALUES (2, ?)",
            (LOCAL_ADMIN_ID,),
        )

        await db.execute(
            "INSERT OR IGNORE INTO classes(id, name, owner_chat_id, timezone) VALUES (1, 'Class-5', ?, ?)",
            (TEACHER1_ID, DEFAULT_TZ),
        )
        await db.execute(
            "INSERT OR IGNORE INTO classes(id, name, owner_chat_id, timezone) VALUES (2, 'Class-6', ?, ?)",
            (TEACHER2_ID, DEFAULT_TZ),
        )

        await db.commit()

    await ensure_user_with_post(LOCAL_ADMIN_ID, post="local_admin", name="Local Admin")
    await ensure_user_with_post(TEACHER1_ID, post="teacher", name="Teacher A")
    await ensure_user_with_post(TEACHER2_ID, post="teacher", name="Teacher B")
    await ensure_user_with_post(STUDENT1_ID, post="student", name="Student A")
    await ensure_user_with_post(STUDENT2_ID, post="student", name="Student B")

    await assign_teacher_to_school(1, TEACHER1_ID)
    await assign_teacher_to_school(2, TEACHER2_ID)
    await assign_student_to_school(1, STUDENT1_ID)
    await assign_student_to_school(2, STUDENT2_ID)


if __name__ == "__main__":
    asyncio.run(seed())
