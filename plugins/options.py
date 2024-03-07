from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from bot import Bot
from models import DB
from models.db import MangaOutput
from output_options import OutputOptions


def get_buttons_for_options(user_options: int):
    buttons = []
    for option in OutputOptions:
        checked = '✅' if option & user_options else '❌'
        text = f'{checked} {option.name}'
        buttons.append([InlineKeyboardButton(text, f'options_{option.value}')])
    return InlineKeyboardMarkup(buttons)


@Bot.on_message(filters.command(['options']))
async def on_options(client: Bot, message: Message):
    db = DB()
    user_options = await db.get(MangaOutput, str(message.from_user.id))
    if not user_options:
        user_options = MangaOutput(user_id=str(message.from_user.id), output=(1 << 30) - 7)
    buttons = get_buttons_for_options(user_options=user_options.output)
    await message.reply('Select the desired output format.', reply_markup=buttons)


@Bot.on_callback_query(filters.regex(r'^options_'))
async def on_callback_query(client, callback: CallbackQuery):
    db = DB()
    user_options = await db.get(MangaOutput, str(callback.from_user.id))
    if not user_options:
        user_options = MangaOutput(user_id=str(callback.from_user.id), output=(1 << 30) - 7)
    option = int(callback.data.split('_')[-1])
    user_options.output ^= option
    buttons = get_buttons_for_options(user_options.output)
    await db.add(user_options)
    await callback.message.edit_reply_markup(reply_markup=buttons)
