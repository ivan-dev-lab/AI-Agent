#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import pytz  # type: ignore

from aiogram import Bot, Dispatcher
from config import default_props
from db import ensure_db
from scheduler_jobs import set_bot, set_scheduler, rehydrate_jobs
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# routers
from handlers.common import router as common_router
from handlers.classes import router as classes_router
from handlers.students import router as students_router
from handlers.enroll import router as enroll_router
from handlers.tasks import router as tasks_router
from handlers.gen import router as gen_router
from handlers.text import router as text_router

from config import BOT_TOKEN

async def main():
    await ensure_db()

    bot = Bot(token=BOT_TOKEN, default=default_props)
    dp = Dispatcher()

    # include routers
    dp.include_router(common_router)
    dp.include_router(classes_router)
    dp.include_router(students_router)
    dp.include_router(enroll_router)
    dp.include_router(tasks_router)
    dp.include_router(gen_router)
    dp.include_router(text_router)

    # scheduler
    scheduler = AsyncIOScheduler(timezone=pytz.utc)
    scheduler.start()
    set_bot(bot)
    set_scheduler(scheduler)
    await rehydrate_jobs()

    print("Bot is running. Press Ctrl+C to stop.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Stopped.")
