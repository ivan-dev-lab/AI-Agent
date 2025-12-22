
import os
import dotenv
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo
from aiogram.client.default import DefaultBotProperties

dotenv.load_dotenv(os.path.abspath('.env'))

BOT_TOKEN = os.getenv("BOT_TOKEN") or ""

if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN в окружении (.env)")

DB_PATH = os.getenv("DB_PATH", "agent.db")

DEFAULT_TZ = os.getenv("DEFAULT_TZ", "Etc/GMT-5")

DEFAULT_TZ_DISPLAY = os.getenv("DEFAULT_TZ_DISPLAY", "UTC+5")

DATETIME_FORMAT = "%d.%m.%Y %H:%M"
DATETIME_FORMAT_DISPLAY = "DD.MM.YYYY HH:MM"
try:
    DEFAULT_TZINFO = ZoneInfo(DEFAULT_TZ)
except Exception:
    DEFAULT_TZINFO = timezone(timedelta(hours=5))
DEFAULT_MODEL = os.getenv("MODEL_NAME", "llama3:8b")
GENAPI_TOKEN = os.getenv("GENAPI_TOKEN", "")
LOCAL_ADMIN_PASSWORD = os.getenv("LOCAL_ADMIN_PASSWORD")



REMINDER_OFFSETS = [
    ("T-7d", timedelta(days=7)),
    ("T-3d", timedelta(days=3)),
    ("T-24h", timedelta(hours=24)),
]

default_props = DefaultBotProperties(parse_mode='HTML')


ENABLE_GEN = True
try:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_community.chat_models import ChatOllama

    SYSTEM_PROMPT = "Ты - лучший помощник по университетским вопросам. Общайся вежливо, уважительно и профессионально"
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
