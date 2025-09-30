# -*- coding: utf-8 -*-
import aiosqlite
from config import DB_PATH

async def fetchone(db, sql: str, params=()):
    cur = await db.execute(sql, params)
    row = await cur.fetchone()
    await cur.close()
    return row

async def fetchall(db, sql: str, params=()):
    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    await cur.close()
    return rows

async def ensure_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = OFF;  -- внешние ключи не используются в этой схеме

-- Таблица классов
CREATE TABLE IF NOT EXISTS classes (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  name           TEXT    NOT NULL UNIQUE,
  owner_chat_id  INTEGER NOT NULL,
  timezone       TEXT    NOT NULL
);

-- Привязки пользователь ↔ класс
CREATE TABLE IF NOT EXISTS enrollments (
  student_id INTEGER NOT NULL,  -- соответствует users.UserID
  class_id   INTEGER NOT NULL,
  UNIQUE (student_id, class_id)
);

-- Задачи
CREATE TABLE IF NOT EXISTS tasks (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  class_id    INTEGER NOT NULL,
  title       TEXT    NOT NULL,
  description TEXT,
  due_utc     TEXT    NOT NULL,
  created_utc TEXT    NOT NULL
);

-- Джобы-напоминания
CREATE TABLE IF NOT EXISTS jobs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    INTEGER NOT NULL,
  run_at_utc TEXT    NOT NULL,
  kind       TEXT    NOT NULL,
  UNIQUE (task_id, run_at_utc, kind)
);

-- Пользователи
-- ВАЖНО: UserID — PRIMARY KEY, НО БЕЗ AUTOINCREMENT (как просили)
CREATE TABLE IF NOT EXISTS "users" (
	"UserID"	INTEGER,
	"name"	TEXT,
	"post"	TEXT NOT NULL,
	"active"	INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY("UserID")
);;

-- Индексы (по желанию, ускоряют выборки)
CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_class   ON enrollments(class_id);
CREATE INDEX IF NOT EXISTS idx_tasks_class         ON tasks(class_id);
CREATE INDEX IF NOT EXISTS idx_jobs_task           ON jobs(task_id);
        """)
        await db.commit()
