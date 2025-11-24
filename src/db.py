import aiosqlite
from typing import Any, Iterable, Optional
from datetime import datetime, timezone

from config import DB_PATH

# ---- базовые утилиты ---------------------------------------------------------
async def fetchone(db, sql: str, params: Iterable[Any] = ()):
    cur = await db.execute(sql, params)
    row = await cur.fetchone()
    await cur.close()
    return row

async def fetchall(db, sql: str, params: Iterable[Any] = ()):
    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    await cur.close()
    return rows

# ---- создание БД --------------------------------------------------------------
async def ensure_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        # чтобы строки были dict-like: row["col"]
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                owner_chat_id INTEGER NOT NULL,
                timezone TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_utc TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                run_at_utc TEXT NOT NULL,
                kind TEXT NOT NULL,
                UNIQUE(task_id, run_at_utc, kind),
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );

            /* Пользователи: UserID — Telegram ID, без AUTOINCREMENT */
            CREATE TABLE IF NOT EXISTS users (
                UserID  INTEGER PRIMARY KEY,
                name    TEXT,
                post    TEXT NOT NULL,
                active  INTEGER NOT NULL DEFAULT 0
            );

            /* Глобальные администраторы (храним только Telegram ID) */
            CREATE TABLE IF NOT EXISTS administrators (
                AdminID INTEGER PRIMARY KEY
            );

            /* Привязки ученик<->класс. student_id = users.UserID */
            CREATE TABLE IF NOT EXISTS enrollments (
                student_id INTEGER NOT NULL,
                class_id   INTEGER NOT NULL,
                UNIQUE (student_id, class_id),
                FOREIGN KEY(student_id) REFERENCES users(UserID) ON DELETE CASCADE,
                FOREIGN KEY(class_id)   REFERENCES classes(id)  ON DELETE CASCADE
            );

            /* === УЧЕБНЫЕ ЗАВЕДЕНИЯ (schools) и роли внутри них === */

            /* Учебные заведения */
            CREATE TABLE IF NOT EXISTS schools (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                short_name  TEXT,
                address     TEXT,
                timezone    TEXT NOT NULL DEFAULT 'UTC',
                created_utc TEXT NOT NULL,
                updated_utc TEXT NOT NULL
            );

            /* Локальные администраторы (users.UserID) по школам */
            CREATE TABLE IF NOT EXISTS school_local_admins (
                school_id INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                PRIMARY KEY (school_id, user_id),
                FOREIGN KEY(school_id) REFERENCES schools(id)   ON DELETE CASCADE,
                FOREIGN KEY(user_id)   REFERENCES users(UserID) ON DELETE CASCADE
            );

            /* Учителя по школам */
            CREATE TABLE IF NOT EXISTS school_teachers (
                school_id INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                PRIMARY KEY (school_id, user_id),
                FOREIGN KEY(school_id) REFERENCES schools(id)   ON DELETE CASCADE,
                FOREIGN KEY(user_id)   REFERENCES users(UserID) ON DELETE CASCADE
            );

            /* Ученики по школам */
            CREATE TABLE IF NOT EXISTS school_students (
                school_id INTEGER NOT NULL,
                user_id   INTEGER NOT NULL,
                PRIMARY KEY (school_id, user_id),
                FOREIGN KEY(school_id) REFERENCES schools(id)   ON DELETE CASCADE,
                FOREIGN KEY(user_id)   REFERENCES users(UserID) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pending_local_admins (
                user_id     INTEGER PRIMARY KEY,
                school_id   INTEGER NOT NULL,
                password    TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                FOREIGN KEY(school_id) REFERENCES schools(id) ON DELETE CASCADE
            );
            """
        )
        await db.commit()

# ---- авторизация/роли ---------------------------------------------------------
async def is_global_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT 1 FROM administrators WHERE AdminID = ? LIMIT 1", (user_id,))
        row = await cur.fetchone()
        await cur.close()
        return row is not None

async def is_known_user(user_id: int) -> bool:
    """Есть ли пользователь в users или administrators."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur1 = await db.execute("SELECT 1 FROM users WHERE UserID = ? LIMIT 1", (user_id,))
        r1 = await cur1.fetchone()
        await cur1.close()
        if r1:
            return True
        cur2 = await db.execute("SELECT 1 FROM administrators WHERE AdminID = ? LIMIT 1", (user_id,))
        r2 = await cur2.fetchone()
        await cur2.close()
        return r2 is not None

# ---- schools helpers -----------------------------------------------------------
async def create_school(
    name: str,
    short_name: Optional[str],
    address: Optional[str],
    tz: str = "UTC",
) -> int:
    """Создать учебное заведение. Возвращает id."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            INSERT INTO schools(name, short_name, address, timezone, created_utc, updated_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, short_name, address, tz, now, now)
        )
        await db.commit()
        return cur.lastrowid

async def list_schools() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(db, "SELECT * FROM schools ORDER BY name COLLATE NOCASE ASC")
        return [dict(r) for r in rows]

# === Schools: helpers for reading/updating ===
from typing import Optional

async def get_school_by_id(school_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await fetchone(db, "SELECT * FROM schools WHERE id = ?", (school_id,))
        return dict(row) if row else None

async def update_school_field(school_id: int, field: str, value) -> None:
    """
    Разрешённые поля: name, short_name, address, timezone.
    Для optional-полей (short_name, address) value=None пишет NULL.
    """
    allowed = {"name", "short_name", "address", "timezone"}
    if field not in allowed:
        raise ValueError("Unsupported field")

    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if value is None and field in {"short_name", "address"}:
            await db.execute(
                f"UPDATE schools SET {field}=NULL, updated_utc=? WHERE id=?",
                (now, school_id)
            )
        else:
            await db.execute(
                f"UPDATE schools SET {field}=?, updated_utc=? WHERE id=?",
                (value, now, school_id)
            )
        await db.commit()

# --- Локальные администраторы ---
async def assign_local_admin(school_id: int, user_id: int) -> bool:
    """Назначить ЛА. Возвращает True, если успешно (включая дубликат)."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO school_local_admins(school_id, user_id) VALUES (?, ?)",
                (school_id, user_id)
            )
            await db.commit()
            return True
        except Exception:
            return False

async def is_user_exists(user_id: int) -> bool:
    """Проверяет, существует ли пользователь в таблице users."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await fetchone(db, "SELECT 1 FROM users WHERE UserID = ?", (user_id,))
        return row is not None
    
import secrets
import string

# --- Pending Local Admins (для приглашений) ---
async def create_pending_la(user_id: int, school_id: int) -> str:
    """Создаёт запись в pending_local_admins и возвращает пароль."""
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO pending_local_admins(user_id, school_id, password, created_utc)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, school_id, password, now)
        )
        await db.commit()
    return password

async def consume_pending_la(user_id: int, password: str) -> Optional[int]:
    """
    Проверяет пароль и активирует ЛА.
    Возвращает school_id, если успешно, иначе None.
    Удаляет запись из pending после успешной активации.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await fetchone(
            db,
            "SELECT school_id, password FROM pending_local_admins WHERE user_id = ?",
            (user_id,)
        )
        if not row or row["password"] != password:
            return None

        school_id = row["school_id"]
        # Удаляем из pending
        await db.execute("DELETE FROM pending_local_admins WHERE user_id = ?", (user_id,))
        # Добавляем в users (если ещё не добавлен)
        await db.execute(
            "INSERT OR IGNORE INTO users(UserID, post, active) VALUES (?, 'local_admin', 1)",
            (user_id,)
        )
        # Назначаем ЛА
        await db.execute(
            "INSERT OR IGNORE INTO school_local_admins(school_id, user_id) VALUES (?, ?)",
            (school_id, user_id)
        )
        await db.commit()
        return school_id
    
# --- ЗАДАНИЯ / КЛАССЫ / ПРЕПОДАВАТЕЛИ ДЛЯ УЧЕНИКА -----------------------------
import aiosqlite
from typing import List, Tuple, Optional

async def list_tasks_for_student(student_id: int, limit: int = 10, offset: int = 0) -> Tuple[list, bool]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(
            db,
            """
            SELECT t.id AS task_id, t.title, t.description, t.due_utc,
                   c.id AS class_id, c.name AS class_name
            FROM enrollments e
            JOIN classes c ON c.id = e.class_id
            JOIN tasks   t ON t.class_id = c.id
            WHERE e.student_id = ?
            ORDER BY datetime(t.due_utc) ASC, t.id ASC
            LIMIT ? OFFSET ?
            """,
            (student_id, limit + 1, offset)
        )
        return rows[:limit], len(rows) > limit

async def get_task_with_class(task_id: int) -> Optional[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await fetchone(
            db,
            """
            SELECT t.id AS task_id, t.title, t.description, t.due_utc,
                   c.id AS class_id, c.name AS class_name
            FROM tasks t
            JOIN classes c ON c.id = t.class_id
            WHERE t.id = ?
            """,
            (task_id,)
        )

async def list_classes_for_student(student_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await fetchall(
            db,
            """
            SELECT c.id, c.name
            FROM enrollments e
            JOIN classes c ON c.id = e.class_id
            WHERE e.student_id = ?
            ORDER BY c.name COLLATE NOCASE
            """,
            (student_id,)
        )

async def list_teachers_for_student(student_id: int) -> list:
    """
    Учителя берутся по школам, где числится ученик: school_students -> school_teachers.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await fetchall(
            db,
            """
            SELECT u.UserID AS teacher_id, COALESCE(u.name, 'Без имени') AS name
            FROM school_students ss
            JOIN school_teachers st ON st.school_id = ss.school_id
            JOIN users u            ON u.UserID    = st.user_id
            WHERE ss.user_id = ?
            GROUP BY u.UserID, u.name
            ORDER BY name COLLATE NOCASE
            """,
            (student_id,)
        )

async def upcoming_tasks_for_student(student_id: int, limit: int = 10) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await fetchall(
            db,
            """
            SELECT t.id AS task_id, t.title, t.due_utc, c.name AS class_name
            FROM enrollments e
            JOIN classes c ON c.id = e.class_id
            JOIN tasks   t ON t.class_id = c.id
            WHERE e.student_id = ?
            ORDER BY datetime(t.due_utc) ASC
            LIMIT ?
            """,
            (student_id, limit)
        )


async def seed_test_data(
    global_admin_ids: Optional[Iterable[int]] = None,
    user_records: Optional[Iterable[Tuple[int, str, str, int]]] = None,
) -> None:
    """
    Заполняет БД тестовыми данными.

    :param global_admin_ids:
        Итерация ID пользователей, которых нужно добавить в таблицу
        глобальных администраторов `administrators(AdminID)`.

    :param user_records:
        Итерация кортежей пользователей для таблицы `users`:
        (user_id, name, post, active)
        где:
            user_id: int  - Telegram ID пользователя
            name: str     - отображаемое имя
            post: str     - должность/роль ('student', 'teacher', 'local_admin', ...)
            active: int   - статус (обычно 1 для активного пользователя)
    """
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # --- 1. Пользователи и глобальные администраторы ---
        if user_records:
            await db.executemany(
                """
                INSERT OR IGNORE INTO users(UserID, name, post, active)
                VALUES (?, ?, ?, ?)
                """,
                list(user_records),
            )

        if global_admin_ids:
            await db.executemany(
                """
                INSERT OR IGNORE INTO administrators(AdminID)
                VALUES (?)
                """,
                [(uid,) for uid in global_admin_ids],
            )

        # --- 2. Тестовые учебные заведения (schools) ---
        schools_data = [
            ("Школа №1", "Шк1", "Город, улица 1", "Europe/Moscow"),
            ("Школа №2", "Шк2", "Город, улица 2", "Europe/Moscow"),
        ]
        school_ids: List[int] = []

        for name, short_name, address, tz in schools_data:
            await db.execute(
                """
                INSERT OR IGNORE INTO schools(name, short_name, address, timezone, created_utc, updated_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, short_name, address, tz, now, now),
            )
            row = await db.execute("SELECT id FROM schools WHERE name = ?", (name,))
            school_row = await row.fetchone()
            if school_row:
                school_ids.append(school_row["id"])

        # --- 3. Привязка ролей по школам (если есть такие пользователи) ---
        # локальные админы
        cur = await db.execute("SELECT UserID FROM users WHERE post = 'local_admin'")
        la_ids = [r["UserID"] for r in await cur.fetchall()]

        # учителя
        cur = await db.execute("SELECT UserID FROM users WHERE post = 'teacher'")
        teacher_ids = [r["UserID"] for r in await cur.fetchall()]

        # ученики
        cur = await db.execute("SELECT UserID FROM users WHERE post = 'student'")
        student_ids = [r["UserID"] for r in await cur.fetchall()]

        # привязки локальных админов к первой школе (если есть)
        if school_ids and la_ids:
            await db.executemany(
                """
                INSERT OR IGNORE INTO school_local_admins(school_id, user_id)
                VALUES (?, ?)
                """,
                [(school_ids[0], uid) for uid in la_ids],
            )

        # привязки учителей ко всем школам (равномерно)
        for idx, tid in enumerate(teacher_ids):
            if not school_ids:
                break
            school_id = school_ids[idx % len(school_ids)]
            await db.execute(
                """
                INSERT OR IGNORE INTO school_teachers(school_id, user_id)
                VALUES (?, ?)
                """,
                (school_id, tid),
            )

        # привязки учеников ко всем школам (равномерно)
        for idx, sid in enumerate(student_ids):
            if not school_ids:
                break
            school_id = school_ids[idx % len(school_ids)]
            await db.execute(
                """
                INSERT OR IGNORE INTO school_students(school_id, user_id)
                VALUES (?, ?)
                """,
                (school_id, sid),
            )

        # --- 4. Тестовые классы и задания ---
        classes_data = [
            ("9А класс",  1000000001, "Europe/Moscow"),
            ("10Б класс", 1000000002, "Europe/Moscow"),
        ]
        class_ids: List[int] = []

        for name, owner_chat_id, tz in classes_data:
            await db.execute(
                """
                INSERT OR IGNORE INTO classes(name, owner_chat_id, timezone)
                VALUES (?, ?, ?)
                """,
                (name, owner_chat_id, tz),
            )
            row = await db.execute("SELECT id FROM classes WHERE name = ?", (name,))
            class_row = await row.fetchone()
            if class_row:
                class_ids.append(class_row["id"])

        # Запишем всех студентов в первый доступный класс
        if class_ids and student_ids:
            await db.executemany(
                """
                INSERT OR IGNORE INTO enrollments(student_id, class_id)
                VALUES (?, ?)
                """,
                [(sid, class_ids[0]) for sid in student_ids],
            )

        # Пара тестовых заданий для каждого класса
        for cid in class_ids:
            await db.execute(
                """
                INSERT INTO tasks(class_id, title, description, due_utc, created_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    "Домашнее задание №1",
                    "Сделать упражнение 1–10.",
                    datetime.now(timezone.utc).isoformat(),
                    now,
                ),
            )
            await db.execute(
                """
                INSERT INTO tasks(class_id, title, description, due_utc, created_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    "Контрольная работа",
                    "Подготовиться к контрольной.",
                    datetime.now(timezone.utc).isoformat(),
                    now,
                ),
            )

        await db.commit()

import asyncio

# asyncio.run(
#     seed_test_data(
#     user_records=[
#         (651213276, "Иван", "student", 1),
#     ],
# )
# )

