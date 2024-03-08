import asyncio

from typing import Dict

from pyrogram.types import CallbackQuery

import filters as flt
from bot import Bot
from tools.sender import send_manga_chapter

locks: Dict[int, asyncio.Lock] = dict()


async def get_user_lock(chat_id: int):
    async with asyncio.Lock():
        lock = locks.get(chat_id)
        if not lock:
            locks[chat_id] = asyncio.Lock()
        return locks[chat_id]


@Bot.on_callback_query(flt.chapter())
async def on_callback_query(client: Bot, callback: CallbackQuery):
    async with await get_user_lock(callback.from_user.id):
        await send_manga_chapter(client, callback.data, callback.from_user.id)
        await asyncio.sleep(5)
