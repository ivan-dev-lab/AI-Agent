
"""
Лёгкий клиент для GenAPI (deepseek-v3).

call_genapi(messages, api_key, endpoint) -> str
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

import aiohttp

DEFAULT_ENDPOINT = "https://api.gen-api.ru/api/v1/networks/deepseek-v3"
DEFAULT_POLL_ENDPOINT = "https://api.gen-api.ru/api/v1/requests"

def _extract_content(data) -> Optional[str]:
    """
    Возвращает только message.content из структуры GenAPI:
    - dict с ключом "result": [ { choices[0].message.content } ]
    - dict с ключом "full_response": [ { choices[0].message.content } ]
    - список таких объектов
    - одиночный объект с choices[0].message.content
    """

    def _from_obj(obj) -> Optional[str]:
        if not isinstance(obj, dict):
            return None
        choices = obj.get("choices")
        if isinstance(choices, list) and choices:
            ch0 = choices[0]
            if isinstance(ch0, dict):
                msg = ch0.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
        return None


    if isinstance(data, dict):

        if isinstance(data.get("result"), list):
            for item in data["result"]:
                text = _from_obj(item)
                if text:
                    return text

        if isinstance(data.get("full_response"), list):
            for item in data["full_response"]:
                text = _from_obj(item)
                if text:
                    return text

        text = _from_obj(data)
        if text:
            return text
        return None


    if isinstance(data, list):
        for obj in data:
            text = _from_obj(obj)
            if text:
                return text
        return None

    return None

async def call_genapi(
    messages: list[dict],
    api_key: str,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout_s: int = 20,
    callback_url: str | None = None,
    poll: bool = True,
    poll_interval: int = 1,
    poll_timeout: int = 60,
    poll_endpoint: str = DEFAULT_POLL_ENDPOINT,
    on_progress: Optional[Callable[[dict], Awaitable[None]]] = None,
) -> str:
    """
    Отправляет массив сообщений в GenAPI deepseek-v3 и возвращает контент ответа.
    При poll=True (по умолчанию) будет автоматически дожидаться завершения генерации
    через /api/v1/requests/<id>, вызывая on_progress при каждом ожидании.
    Сообщения ожидаются в формате [{"role": "user" | "system" | "assistant", "content": "..."}].
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {"messages": messages}
    if callback_url:
        payload["callback_url"] = callback_url

    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(endpoint, json=payload, headers=headers) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise RuntimeError(f"HTTP {resp.status}: {text}")
            data = await resp.json()


        if poll and isinstance(data, dict) and data.get("status") == "processing" and data.get("request_id"):
            request_id = data["request_id"]
            end_ts = asyncio.get_event_loop().time() + poll_timeout

            if on_progress:
                await on_progress(data)

            base_api = "/".join(endpoint.split("/")[:3])
            poll_urls = [
                f"{base_api}/api/v1/request/get/{request_id}",
                f"{poll_endpoint.rstrip('/')}/{request_id}",
                f"{endpoint.rstrip('/')}/requests/{request_id}",
                f"{endpoint.rstrip('/')}/{request_id}",
                f"{endpoint.rsplit('/', 1)[0]}/requests/{request_id}",
                f"{endpoint.rsplit('/', 1)[0]}/{request_id}",
                f"{base_api}/api/v1/requests/{request_id}",
                f"{base_api}/api/v1/networks/requests/{request_id}",
                f"{base_api}/api/v1/networks/deepseek-v3/requests/{request_id}",
            ]
            poll_urls += [u + suffix for u in poll_urls for suffix in ("/status", "/result")]
            consecutive_404 = 0
            url_idx = 0
            best_content: Optional[str] = None
            while asyncio.get_event_loop().time() < end_ts:
                await asyncio.sleep(poll_interval)
                url = poll_urls[url_idx % len(poll_urls)]
                url_idx += 1
                async with session.get(url, headers=headers) as resp:

                    if resp.status in (404, 405):
                        consecutive_404 += 1
                        if consecutive_404 >= len(poll_urls) * 2:
                            break
                        continue
                    consecutive_404 = 0
                    if resp.status >= 400:
                        text = await resp.text()
                        raise RuntimeError(f"HTTP {resp.status}: {text}")
                    data = await resp.json()
                if on_progress:
                    await on_progress(data)

                if isinstance(data, dict) and data.get("status") and data.get("status") != "processing":
                    break

                best_content = _extract_content(data) or best_content
                if best_content:
                    break

            if best_content:
                return best_content.strip()

    content = _extract_content(data)
    if isinstance(content, str):
        return content.strip()
    if content is not None:
        return str(content).strip()
    return str(data).strip()
