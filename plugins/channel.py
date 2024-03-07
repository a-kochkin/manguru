from datetime import datetime, timedelta

from loguru import logger
from pyrogram import filters, ContinuePropagation, StopPropagation
from pyrogram.errors import UsernameNotOccupied, ChatAdminRequired, UserNotParticipant
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot import Bot, users_in_channel
from config import env_vars


@Bot.on_message(~(filters.private & filters.incoming))
async def on_chat_or_channel_message(client: Bot, message: Message):
    pass


@Bot.on_message(filters.private)
async def on_private_message(client: Bot, message: Message):
    channel = env_vars.get('CHANNEL')
    if not channel:
        return message.continue_propagation()
    if in_channel_cached := users_in_channel.get(message.from_user.id):
        if datetime.now() - in_channel_cached < timedelta(days=1):
            return message.continue_propagation()
    try:
        if await client.get_chat_member(channel, message.from_user.id):
            users_in_channel[message.from_user.id] = datetime.now()
            return message.continue_propagation()
    except UsernameNotOccupied:
        logger.debug('Channel does not exist, therefore bot will continue to operate normally')
        return message.continue_propagation()
    except ChatAdminRequired:
        logger.debug('Bot is not admin of the channel, therefore bot will continue to operate normally')
        return message.continue_propagation()
    except UserNotParticipant:
        await message.reply("In order to use the bot you must join it's update channel.'",
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton('Join!', url=f't.me/{channel}')]]
                            ))
    except ContinuePropagation:
        raise
    except StopPropagation:
        raise
    except BaseException as e:
        logger.exception(e)
