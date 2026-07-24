from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.config import Settings


class AccessMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        allowed = self.settings.allowed_ids
        if not allowed:
            return await handler(event, data)

        user = data.get("event_from_user")
        if user is None or user.id not in allowed:
            if isinstance(event, Message):
                await event.answer("⛔ Доступ к боту ограничен.")
            return None
        return await handler(event, data)
