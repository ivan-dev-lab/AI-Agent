
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from io import BytesIO

from config import ENABLE_GEN, DEFAULT_MODEL, PROMPT, PARSER, build_llm
from keyboards import back_kb
from callbacks import CB_GEN
from utils import extract_code_from_markdown, make_py_document

router = Router()

@router.callback_query(F.data == CB_GEN)
async def cb_gen(cq: CallbackQuery):
    from handlers.text import USER_STATE
    USER_STATE[cq.from_user.id] = {"mode": "gen", "step": 0, "data": {}, "chat_id": cq.message.chat.id}
    await cq.message.edit_text(
        "🤖 <b>Генерация MicroPython</b>\n\n"
        "Шаг 1/1: опишите задание текстом. Пример:\n"
        "<i>Кнопка на GPIO12 включает LED на GPIO2 на 3 секунды, PWM 50%</i>\n",
        reply_markup=back_kb()
    )

async def _run_generation(msg: Message, desc: str):
    if not ENABLE_GEN:
        return await msg.answer("Генерация временно недоступна (нет LangChain/Ollama).", reply_markup=back_kb())
    model_name = DEFAULT_MODEL
    llm = build_llm(model_name)
    chain = PROMPT | llm | PARSER
    await msg.answer("Генерирую код, подождите 5–15 секунд...", reply_markup=back_kb())
    try:
        result = await chain.ainvoke({"task_description": desc})
    except Exception as e:
        return await msg.answer(f"Ошибка запроса к модели: {e}", reply_markup=back_kb())

    code = extract_code_from_markdown(result)
    file = make_py_document("micropython_task.py", code)
    await msg.answer_document(file, caption="Готово! Проверьте пины и параметры.", reply_markup=back_kb())
    if len(result) < 3500:
        await msg.answer(result, reply_markup=back_kb())
