from typing import AsyncIterator, List

from openai import AsyncOpenAI

from ai.base_provider import BaseLLMProvider, Message
from config import cfg

DEFAULT_MODEL = "gpt-4o"
MAX_TOKENS = 1024


class OpenAIProvider(BaseLLMProvider):

    def __init__(self):
        kwargs = {"api_key": cfg.openai_api_key}
        if cfg.openai_base_url:
            kwargs["base_url"] = cfg.openai_base_url
            if "openrouter" in cfg.openai_base_url:
                kwargs["default_headers"] = {
                    "HTTP-Referer": "https://zuki.ai",
                    "X-Title": "Zuki",
                }
        self._client = AsyncOpenAI(**kwargs)

    async def stream_response(
        self,
        user_text: str,
        screenshots_b64: List[str],
        history: List[Message],
        system_prompt: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        model = model or cfg.openai_model or DEFAULT_MODEL

        messages = [{"role": "system", "content": system_prompt}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        if screenshots_b64:
            content: list = []
            for img_b64 in screenshots_b64:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"},
                })
            content.append({"type": "text", "text": user_text})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_text})

        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=MAX_TOKENS,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def health_check(self) -> bool:
        try:
            if cfg.openai_base_url and "openrouter" in cfg.openai_base_url:
                return bool(cfg.openai_api_key)
            await self._client.models.list()
            return True
        except Exception:
            return False
