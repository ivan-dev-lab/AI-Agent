import aiosqlite
import secrets          # ← добавлено
import string           # ← добавлено

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
                owner_chat_id INTEGER NOT NULL
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
             CREATE TABLE IF NOT EXISTS pending_students (
                token        TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                class_id     INTEGER NOT NULL,
                created_by   INTEGER,
                created_utc  TEXT NOT NULL,
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
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
            /* Приглашения учеников (для ссылок-приглашений по start param) */
            CREATE TABLE IF NOT EXISTS pending_students (
                token        TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                class_id     INTEGER NOT NULL,
                created_by   INTEGER,
                created_utc  TEXT NOT NULL,
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS task_targets (
                task_id    INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                PRIMARY KEY (task_id, student_id),
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY(student_id) REFERENCES users(UserID) ON DELETE CASCADE
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
    # --- Pending Students (приглашения учеников) -------------------------------

async def create_pending_student(
    display_name: str,
    class_id: int,
    created_by: int | None = None,
) -> str:
    """
    Создаёт приглашение ученика и возвращает токен.
    Логика как в учителе.
    """
    token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO pending_students(token, display_name, class_id, created_by, created_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token, display_name, class_id, created_by, now)
        )
        await db.commit()
    return token


async def consume_pending_student(token: str, user_id: int) -> Optional[tuple[int, str]]:
    """
    Активирует приглашение ученика:
    - добавляет пользователя в users с ролью 'student' (если ещё нет),
    - записывает в указанный класс (enrollments),
    - удаляет приглашение.
    Возвращает (class_id, display_name) при успехе, иначе None.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await fetchone(
            db,
            "SELECT display_name, class_id FROM pending_students WHERE token = ?",
            (token,)
        )
        if not row:
            return None

        display_name = row["display_name"]
        class_id = row["class_id"]

        # создаём/активируем ученика
        await db.execute(
            "INSERT OR IGNORE INTO users(UserID, name, post, active) VALUES(?, ?, 'student', 1)",
            (user_id, display_name)
        )
        # записываем в класс
        await db.execute(
            "INSERT OR IGNORE INTO enrollments(student_id, class_id) VALUES(?, ?)",
            (user_id, class_id)
        )
        # удаляем приглашение
        await db.execute("DELETE FROM pending_students WHERE token = ?", (token,))
        await db.commit()

    return class_id, display_name

    
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
    # ----------------- Helpers for Local Admin operations -----------------------  # ← добавлено

# === добавлено блок ===
async def _get_school_ids_for_la(la_user_id: int) -> list:
    """Возвращает список id школ, к которым привязан локальный админ."""
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await fetchall(db, "SELECT school_id FROM school_local_admins WHERE user_id = ?", (la_user_id,))
        return [r["school_id"] for r in rows] if rows else []
    
async def list_local_admins() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(db, """
            SELECT u.UserID, u.name, s.school_id, sc.name AS school_name
            FROM users u
            JOIN school_local_admins s ON u.UserID = s.user_id
            JOIN schools sc ON s.school_id = sc.id
            WHERE u.post = 'local_admin'
            ORDER BY u.UserID
        """)
        return [dict(r) for r in rows]

async def create_student_for_school(user_id: int, la_user_id: int) -> bool:
    """Добавляет пользователя как ученика в школу(ы) локального админа."""
    school_ids = await _get_school_ids_for_la(la_user_id)
    if not school_ids:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT OR IGNORE INTO users(UserID, post, active) VALUES (?, 'student', 1)", (user_id,))
            for sid in school_ids:
                await db.execute("INSERT OR IGNORE INTO school_students(school_id, user_id) VALUES (?, ?)", (sid, user_id))
            await db.commit()
            return True
        except Exception:
            return False
        
async def create_teacher_for_school(user_id: int, la_user_id: int) -> bool:
    """Добавляет пользователя как учителя в школу(ы) локального админа."""
    school_ids = await _get_school_ids_for_la(la_user_id)
    if not school_ids:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO users(UserID, post, active) VALUES (?, 'teacher', 1)",
                (user_id,)
            )
            for sid in school_ids:
                await db.execute(
                    "INSERT OR IGNORE INTO school_teachers(school_id, user_id) VALUES (?, ?)",
                    (sid, user_id)
                )
            await db.commit()
            return True
        except Exception:
            return False
       
    


async def generate_temp_password() -> str:
    """Генерирует временный пароль для приглашений."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(10))


async def register_pending_teacher(user_id: int, la_user_id: int):
    """Добавляет временного учителя, ожидающего подтверждения."""
    password = await generate_temp_password()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_teachers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                la_user_id INTEGER,
                password TEXT
            )
        """)
        await db.execute("INSERT INTO pending_teachers(user_id, la_user_id, password) VALUES (?, ?, ?)",
                         (user_id, la_user_id, password))
        await db.commit()
    return password


async def get_pending_teachers(la_user_id: int):
    """Возвращает список ожидающих подтверждения учителей."""
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await fetchall(db, "SELECT user_id, password FROM pending_teachers WHERE la_user_id = ?", (la_user_id,))
        return rows
# === конец добавленного блока ===1
# ---------------------------------------------------------------------------
#            Хелперы для локального администратора (списки)
# ---------------------------------------------------------------------------

async def _get_school_ids_for_la(la_user_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(
            db,
            "SELECT school_id FROM school_local_admins WHERE user_id = ?",
            (la_user_id,)
        )
        return [r["school_id"] for r in rows]


async def list_teachers_for_la(la_user_id: int) -> list[dict]:
    school_ids = await _get_school_ids_for_la(la_user_id)
    if not school_ids:
        return []

    placeholders = ",".join("?" * len(school_ids))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(
            db,
            f"""
            SELECT DISTINCT u.UserID, COALESCE(u.name, 'Без имени') AS name
            FROM school_teachers st
            JOIN users u ON u.UserID = st.user_id
            WHERE st.school_id IN ({placeholders})
            ORDER BY name COLLATE NOCASE
            """,
            tuple(school_ids)
        )
        return [dict(r) for r in rows]


async def list_students_for_la(la_user_id: int) -> list[dict]:
    school_ids = await _get_school_ids_for_la(la_user_id)
    if not school_ids:
        return []

    placeholders = ",".join("?" * len(school_ids))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(
            db,
            f"""
            SELECT DISTINCT u.UserID, COALESCE(u.name, 'Без имени') AS name
            FROM school_students ss
            JOIN users u ON u.UserID = ss.user_id
            WHERE ss.school_id IN ({placeholders})
            ORDER BY name COLLATE NOCASE
            """,
            tuple(school_ids)
        )
        return [dict(r) for r in rows]


async def list_local_admins_for_la(la_user_id: int) -> list[dict]:
    school_ids = await _get_school_ids_for_la(la_user_id)
    if not school_ids:
        return []

    placeholders = ",".join("?" * len(school_ids))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(
            db,
            f"""
            SELECT DISTINCT u.UserID, COALESCE(u.name, 'Без имени') AS name
            FROM school_local_admins sla
            JOIN users u ON u.UserID = sla.user_id
            WHERE sla.school_id IN ({placeholders})
            ORDER BY name COLLATE NOCASE
            """,
            tuple(school_ids)
        )
        return [dict(r) for r in rows]


# --- Pending Students (инвайты для учеников) ---
import secrets
import string

async def create_pending_student(display_name: str, class_id: int, created_by: int | None = None) -> str:
    token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO pending_students(token, display_name, class_id, created_by, created_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token, display_name, class_id, created_by, now)
        )
        await db.commit()
    return token

async def consume_pending_student(token: str, user_id: int) -> tuple[int, str] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await fetchone(db, "SELECT display_name, class_id FROM pending_students WHERE token = ?", (token,))
        if not row:
            return None

        display_name = row["display_name"]
        class_id = row["class_id"]

        await db.execute(
            "INSERT OR IGNORE INTO users(UserID, name, post, active) VALUES (?, ?, 'student', 1)",
            (user_id, display_name)
        )
        await db.execute(
            "UPDATE users SET name = COALESCE(name, ?) WHERE UserID = ?",
            (display_name, user_id)
        )
        await db.execute(
            "INSERT OR IGNORE INTO enrollments(student_id, class_id) VALUES (?, ?)",
            (user_id, class_id)
        )
        await db.execute("DELETE FROM pending_students WHERE token = ?", (token,))
        await db.commit()

        return (class_id, display_name)

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
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

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

        cur = await db.execute("SELECT UserID FROM users WHERE post = 'local_admin'")
        la_ids = [r["UserID"] for r in await cur.fetchall()]

        cur = await db.execute("SELECT UserID FROM users WHERE post = 'teacher'")
        teacher_ids = [r["UserID"] for r in await cur.fetchall()]

        cur = await db.execute("SELECT UserID FROM users WHERE post = 'student'")
        student_ids = [r["UserID"] for r in await cur.fetchall()]

        if school_ids and la_ids:
            await db.executemany(
                """
                INSERT OR IGNORE INTO school_local_admins(school_id, user_id)
                VALUES (?, ?)
                """,
                [(school_ids[0], uid) for uid in la_ids],
            )

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

        if class_ids and student_ids:
            await db.executemany(
                """
                INSERT OR IGNORE INTO enrollments(student_id, class_id)
                VALUES (?, ?)
                """,
                [(sid, class_ids[0]) for sid in student_ids],
            )

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

# ---------------------------------------------------------------------------
#                 ДОБАВЛЕНО: УТИЛИТЫ ДЛЯ УЧИТЕЛЕЙ/УЧЕНИКОВ (ГА)
# ---------------------------------------------------------------------------

async def ensure_user_with_post(user_id: int, post: str, name: str | None = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users(UserID, name, post, active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(UserID) DO UPDATE SET
                post = excluded.post,
                active = 1,
                name = COALESCE(excluded.name, name)
            """,
            (user_id, name, post)
        )
        await db.commit()

async def set_user_name(user_id: int, name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET name = ? WHERE UserID = ?", (name, user_id))
        await db.commit()

async def assign_teacher_to_school(school_id: int, user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO school_teachers(school_id, user_id) VALUES (?,?)", (school_id, user_id))
        await db.commit()

async def assign_student_to_school(school_id: int, user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO school_students(school_id, user_id) VALUES (?,?)", (school_id, user_id))
        await db.commit()

async def remove_teacher_from_school(school_id: int, user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM school_teachers WHERE school_id = ? AND user_id = ?", (school_id, user_id))
        await db.commit()

async def remove_student_from_school(school_id: int, user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM school_students WHERE school_id = ? AND user_id = ?", (school_id, user_id))
        await db.commit()

async def list_school_teachers(school_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(
            db,
            """
            SELECT u.UserID AS user_id, COALESCE(u.name, 'Без имени') AS name
            FROM school_teachers st
            JOIN users u ON u.UserID = st.user_id
            WHERE st.school_id = ?
            ORDER BY name COLLATE NOCASE
            """,
            (school_id,)
        )
        return [dict(r) for r in rows]

async def list_school_students(school_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(
            db,
            """
            SELECT u.UserID AS user_id, COALESCE(u.name, 'Без имени') AS name
            FROM school_students ss
            JOIN users u ON u.UserID = ss.user_id
            WHERE ss.school_id = ?
            ORDER BY name COLLATE NOCASE
            """,
            (school_id,)
        )
        return [dict(r) for r in rows]


# === НОВОЕ: список глобальных администраторов (для инфо-меню) ===
async def list_global_admins() -> list[dict]:
    """
    Возвращает всех глобальных администраторов.
    Формат: [{"user_id": int, "name": str}]
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await fetchall(
            db,
            """
            SELECT a.AdminID AS user_id, COALESCE(u.name, 'Без имени') AS name
            FROM administrators a
            LEFT JOIN users u ON u.UserID = a.AdminID
            ORDER BY a.AdminID
            """
        )
        return [dict(r) for r in rows]
