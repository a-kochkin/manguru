from pathlib import Path

from pyrogram import filters
from pyrogram.types import Message

from bot import Bot

with open(Path(__file__).absolute().parent.parent / 'tools/help_message.txt', 'r') as f:
    help_msg = f.read()


@Bot.on_message(filters.command(['help']))
async def on_help(client: Bot, message: Message):
    await message.reply(help_msg)
