from pyrogram import filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot import Bot, mangas
from models import DB, Subscription, MangaName


def is_fav_in_dict(_, client: Bot, callback: CallbackQuery):
    fil = callback.data.startswith('fav') or callback.data.startswith('unfav')

    if not fil:
        return False

    data = callback.data.split('_')[1]

    return data in mangas


@Bot.on_message(filters.command(['favourites']))
async def on_subs(client: Bot, message: Message):
    db = DB()

    filter_ = message.text.split(maxsplit=1)[1] if message.text.split(maxsplit=1)[1:] else ''
    filter_list = [filter_.strip() for filter_ in filter_.split(' ') if filter_.strip()]

    subs = await db.get_subs(str(message.from_user.id), filter_list)

    lines = []
    for sub in subs[:10]:
        lines.append(f'<a href="{sub.url}">{sub.name}</a>')
        lines.append(f'`/cancel {sub.url}`')
        lines.append('')

    if not lines:
        if filter_:
            return await message.reply('You have no subscriptions with that filter.')
        return await message.reply('You have no subscriptions yet.')

    text = '\n'.join(lines)
    await message.reply(f'Your subscriptions:\n\n{text}\nTo see more subscriptions use `/subs filter`',
                        disable_web_page_preview=True)


@Bot.on_message(filters.regex(r'^/cancel ([^ ]+)$'))
async def on_cancel(client: Bot, message: Message):
    db = DB()
    sub = await db.get(Subscription, (message.matches[0].group(1), str(message.from_user.id)))
    if not sub:
        return await message.reply('You were not subscribed to that manga.')
    await db.erase(sub)
    return await message.reply('You will no longer receive updates for that manga.')


@Bot.on_callback_query(filters.create(is_fav_in_dict))
async def on_callback_query(client, callback: CallbackQuery):
    action, data = callback.data.split('_')
    fav = action == 'fav'
    manga = mangas[data]
    db = DB()
    subs = await db.get(Subscription, (manga.url, str(callback.from_user.id)))
    if not subs and fav:
        await db.add(Subscription(url=manga.url, user_id=str(callback.from_user.id)))
    if subs and not fav:
        await db.erase(subs)
    if subs and fav:
        await callback.answer("You are already subscribed", show_alert=True)
    if not subs and not fav:
        await callback.answer("You are not subscribed", show_alert=True)
    reply_markup = callback.message.reply_markup
    keyboard = reply_markup.inline_keyboard
    keyboard[0] = [InlineKeyboardButton(
        "Unsubscribe" if fav else "Subscribe",
        f"{'unfav' if fav else 'fav'}_{data}"
    )]
    await callback.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    db_manga = await db.get(MangaName, manga.url)
    if not db_manga:
        await db.add(MangaName(url=manga.url, name=manga.name))
