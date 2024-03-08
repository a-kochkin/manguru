from pyrogram.errors import BadRequest
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import filters as flt
from bot import Bot, mangas, chapters
from clients import MangaCard
from models import Subscription, DB
from pagination import Pagination


async def get_buttons_for_chapters(manga: MangaCard, user_id: int, page: int):

    db = DB()
    subs = await db.get(Subscription, (manga.url, str(user_id)))

    fav = [[InlineKeyboardButton(
        "Unsubscribe" if subs else "Subscribe",
        f"{'unfav' if subs else 'fav'}_{manga.unique()}"
    )]]

    pagination = Pagination()
    pagination.chapters = manga.chapters
    results = pagination.get_page_chapters(page)

    footer = []
    prev = pagination.get_prev_page(page)
    next_ = pagination.get_next_page(page)
    if prev:
        footer.append(InlineKeyboardButton('<<', callback_data=f'pagination_{manga.unique()}_{prev}'))
    if next_:
        footer.append(InlineKeyboardButton('>>', callback_data=f'pagination_{manga.unique()}_{next_}'))

    main = [[InlineKeyboardButton(result.name, callback_data=result.unique())] for result in results]

    return InlineKeyboardMarkup(fav + [footer] + main + [footer])


@Bot.on_message(flt.manga())
async def on_message(client: Bot, message: Message):
    manga = mangas[message.text]

    await manga.client.set_chapters(manga)
    for chapter in manga.chapters:
        chapters[chapter.unique()] = chapter

    buttons = await get_buttons_for_chapters(manga, message.from_user.id, 1)

    try:
        await message.reply_photo(manga.picture_url,
                                  caption=f'{manga.name}\n'
                                          f'{manga.get_url()}', reply_markup=buttons)
    except BadRequest:
        file_name = f'pictures/{manga.unique()}.jpg'
        await manga.client.get_cover(manga, cache=True, file_name=file_name)
        await message.reply_photo(f'./cache/{manga.client.name}/{file_name}',
                                  caption=f'{manga.name}\n'
                                          f'{manga.get_url()}', reply_markup=buttons)


@Bot.on_callback_query(flt.manga('pagination_'))
async def on_callback_query(client, callback: CallbackQuery):
    manga = mangas[callback.data.split('_')[1]]
    page = int(callback.data.split('_')[2])

    buttons = await get_buttons_for_chapters(manga, callback.from_user.id, page)

    await callback.edit_message_reply_markup(buttons)
