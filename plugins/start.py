from pathlib import Path

from loguru import logger
from pyrogram import filters
from pyrogram.types import Message

from bot import Bot

with open(Path(__file__).absolute().parent.parent / 'tools/start_message.txt', 'r') as f:
    start_msg = f.read()


@Bot.on_message(filters.command(['start']))
async def on_start(client: Bot, message: Message):
    logger.info(f'User {message.from_user.id} started the bot')
    await message.reply(start_msg)
    logger.info(f'User {message.from_user.id} finished the start command')
