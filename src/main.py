# src/main.py
import asyncio
import os
import dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, default_props
from db import ensure_db
from handlers.common import router as common_router
from handlers.enroll import router as enroll_router
from handlers.tasks import router as tasks_router
from handlers.students import router as students_router
from handlers.classes import router as classes_router
from handlers.gen import router as gen_router
from handlers.text import router as text_router
from handlers.admin_global import router as ga_router  # NEW

dotenv.load_dotenv()

async def main():
    await ensure_db()

    bot = Bot(token=BOT_TOKEN, default=default_props)
    dp = Dispatcher()

    # routers
    dp.include_router(common_router)
    dp.include_router(ga_router)        # NEW: меню глобального администратора
    dp.include_router(enroll_router)
    dp.include_router(tasks_router)
    dp.include_router(students_router)
    dp.include_router(classes_router)
    dp.include_router(gen_router)
    dp.include_router(text_router)

    print("Bot is running. Press Ctrl+C to stop.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Stopped.")
