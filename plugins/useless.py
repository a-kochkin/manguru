from pyrogram import filters
from pyrogram.types import Message, InlineQuery, CallbackQuery

from bot import Bot


@Bot.on_message(filters.regex(r'^/'))
async def on_unknown_command(client: Bot, message: Message):
    await message.reply('Unknown command')


@Bot.on_inline_query()
async def on_inline_query(client: Bot, inline_query: InlineQuery):
    await inline_query.answer([])


@Bot.on_callback_query()
async def on_callback_query(client, callback: CallbackQuery):
    await callback.answer('This is an old button, please redo the search', show_alert=True)

