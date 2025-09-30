# -*- coding: utf-8 -*-
import os
import dotenv
from datetime import timedelta
from aiogram.client.default import DefaultBotProperties

dotenv.load_dotenv(os.path.abspath('AI-Agent/.env'))

BOT_TOKEN = os.getenv("BOT_TOKEN") or ""

if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN в окружении (.env)")

DB_PATH = os.getenv("DB_PATH", "agent.db")
DEFAULT_TZ = os.getenv("DEFAULT_TZ", "UTC")
DEFAULT_MODEL = os.getenv("MODEL_NAME", "llama3:8b")

# напоминания для заданий
REMINDER_OFFSETS = [
    ("T-24h", timedelta(hours=24)),
    ("T-3h", timedelta(hours=3)),
    ("T-15m", timedelta(minutes=15)),
    ("T0", timedelta(seconds=0)),
]

default_props = DefaultBotProperties(parse_mode='HTML')

# --- генерация кода (Ollama / LangChain) ---
ENABLE_GEN = True  # можно отключить если не нужно
try:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_community.chat_models import ChatOllama

    SYSTEM_PROMPT = """\
You are an expert MicroPython tutor for ESP32-based educational robotics.
Your job: generate clean, safe, well-commented MicroPython code **first**, then include a short explanation at the end.
Constraints and style:
- Target platform: ESP32 with MicroPython standard modules only (machine, time, PWM etc.). Avoid uasyncio unless explicitly requested.
- No external libraries. No network unless explicitly requested.
- Always declare GPIO pins as named constants at the top (e.g., LED_PIN = 2).
- Use clear function structure, docstrings, and step-by-step comments for students.
- Add a short "Test Instructions" section as comments.
- If hardware is ambiguous, make safe assumptions and clearly list them in comments.
Return code enclosed in Markdown triple backticks with language 'python', then the explanation.
"""
    PROMPT = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human",
         "Generate MicroPython code for ESP32 according to this description:\n"
         "=== DESCRIPTION START ===\n{task_description}\n=== DESCRIPTION END ===\n\n"
         "Make the code beginner-friendly with comments; then add a short explanation.")
    ])
    PARSER = StrOutputParser()

    def build_llm(model_name: str) -> "ChatOllama":
        return ChatOllama(model=model_name, temperature=0.2)

except Exception:
    ENABLE_GEN = False
    PROMPT = None
    PARSER = None

