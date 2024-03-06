import asyncio
import datetime as dt
import enum
import os
import re
import shutil
from typing import Dict

import pyrogram.errors
from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineQuery, \
    InlineKeyboardMarkup, InlineKeyboardButton, InputMediaDocument, InlineQueryResultArticle, \
    InputTextMessageContent

from config import env_vars, dbname
from img2cbz.core import fld2cbz
from img2pdf.core import fld2pdf, fld2thumb
from img2tph.core import img2tph
from models.db import DB, ChapterFile, Subscription, MangaOutput
from pagination import Pagination
from plugins import MangaClient, MangaCard, MangaChapter, \
    ReadMangaClient, MintMangaClient
from plugins.client import clean
from tools.flood import retry_on_flood

mangas: Dict[str, MangaCard] = dict()
chapters: Dict[str, MangaChapter] = dict()
pdfs: Dict[str, str] = dict()
paginations: Dict[int, Pagination] = dict()
users_in_channel: Dict[int, dt.datetime] = dict()
locks: Dict[int, asyncio.Lock] = dict()

plugin_dicts: Dict[str, Dict[str, MangaClient]] = {
    '🇷🇺 RU': {
        'ReadManga': ReadMangaClient(),
        'MintManga': MintMangaClient()
    }
}

cache_dir = 'cache'
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)

with open('tools/start_message.txt', 'r') as f:
    start_msg = f.read()

with open('tools/help_message.txt', 'r') as f:
    help_msg = f.read()


class OutputOptions(enum.IntEnum):
    PDF = 1
    CBZ = 2
    Telegraph = 4

    def __and__(self, other):
        return self.value & other

    def __xor__(self, other):
        return self.value ^ other

    def __or__(self, other):
        return self.value | other


disabled = []

plugins = dict()
for plugin_lang, plugin_dict in plugin_dicts.items():
    for name, plugin in plugin_dict.items():
        identifier = f'[{plugin_lang}] {name}'
        if identifier in disabled:
            continue
        plugins[identifier] = plugin

subsPaused = disabled + []


def split_list(li):
    return [li[x: x + 2] for x in range(0, len(li), 2)]


def get_buttons_for_options(user_options: int):
    buttons = []
    for option in OutputOptions:
        checked = '✅' if option & user_options else '❌'
        text = f'{checked} {option.name}'
        buttons.append([InlineKeyboardButton(text, f'options_{option.value}')])
    return InlineKeyboardMarkup(buttons)


def get_buttons_for_chapters(pagination: Pagination):
    results = pagination.get_chapters()

    prev = InlineKeyboardButton('<<', f'{pagination.id}_{pagination.page - 1}')
    next_ = InlineKeyboardButton('>>', f'{pagination.id}_{pagination.page + 1}')

    footer = []
    if not pagination.is_first_page:
        footer.append(prev)
    if not pagination.is_last_page:
        footer.append(next_)

    return InlineKeyboardMarkup([footer] + [
        [InlineKeyboardButton(result.name, result.unique())] for result in results
    ] + [footer])


bot = Client('bot',
             api_id=int(env_vars.get('API_ID')),
             api_hash=env_vars.get('API_HASH'),
             bot_token=env_vars.get('BOT_TOKEN'),
             max_concurrent_transmissions=3)

if dbname:
    DB(dbname)
else:
    DB()


def manga_unique_filter(_, client: Client, message: Message):
    return message.text in mangas


@bot.on_message(filters=~(filters.private & filters.incoming))
async def on_chat_or_channel_message(client: Client, message: Message):
    pass


@bot.on_message()
async def on_private_message(client: Client, message: Message):
    channel = env_vars.get('CHANNEL')
    if not channel:
        return message.continue_propagation()
    if in_channel_cached := users_in_channel.get(message.from_user.id):
        if dt.datetime.now() - in_channel_cached < dt.timedelta(days=1):
            return message.continue_propagation()
    try:
        if await client.get_chat_member(channel, message.from_user.id):
            users_in_channel[message.from_user.id] = dt.datetime.now()
            return message.continue_propagation()
    except pyrogram.errors.UsernameNotOccupied:
        logger.debug('Channel does not exist, therefore bot will continue to operate normally')
        return message.continue_propagation()
    except pyrogram.errors.ChatAdminRequired:
        logger.debug('Bot is not admin of the channel, therefore bot will continue to operate normally')
        return message.continue_propagation()
    except pyrogram.errors.UserNotParticipant:
        await message.reply("In order to use the bot you must join it's update channel.'",
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton('Join!', url=f't.me/{channel}')]]
                            ))
    except pyrogram.ContinuePropagation:
        raise
    except pyrogram.StopPropagation:
        raise
    except BaseException as e:
        logger.exception(e)


@bot.on_message(filters=filters.command(['start']))
async def on_start(client: Client, message: Message):
    logger.info(f'User {message.from_user.id} started the bot')
    await message.reply(start_msg)
    logger.info(f'User {message.from_user.id} finished the start command')


@bot.on_message(filters=filters.command(['search']))
async def on_search(client: Client, message: Message):
    await message.reply('Select search languages.', reply_markup=InlineKeyboardMarkup(
        split_list([InlineKeyboardButton(language, callback_data=f'search_{language}')
                    for language in plugin_dicts.keys()])
    ))


@bot.on_message(filters=filters.command(['help']))
async def on_help(client: Client, message: Message):
    await message.reply(help_msg)


@bot.on_message(filters=filters.command(['refresh']))
async def on_refresh(client: Client, message: Message):
    text = message.reply_to_message.text or message.reply_to_message.caption
    if text:
        regex = re.compile(r'\[Read on telegraph]\((.*)\)')
        match = regex.search(text.markdown)
    else:
        match = None
    document = message.reply_to_message.document
    if not (message.reply_to_message and message.reply_to_message.outgoing and
            ((document and document.file_name[-4:].lower() in ['.pdf', '.cbz']) or match)):
        return await message.reply('This command only works when it replies to a manga file that bot sent to you')
    db = DB()
    if document:
        chapter = await db.get_chapter_file_by_id(document.file_unique_id)
    else:
        chapter = await db.get_chapter_file_by_id(match.group(1))
    if not chapter:
        return await message.reply('This file was already refreshed')
    await db.erase(chapter)
    return await message.reply('File refreshed successfully!')


@bot.on_message(filters=filters.command(['subs']))
async def on_subs(client: Client, message: Message):
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


@bot.on_message(filters=filters.regex(r'^/cancel ([^ ]+)$'))
async def on_cancel(client: Client, message: Message):
    db = DB()
    sub = await db.get(Subscription, (message.matches[0].group(1), str(message.from_user.id)))
    if not sub:
        return await message.reply('You were not subscribed to that manga.')
    await db.erase(sub)
    return await message.reply('You will no longer receive updates for that manga.')


@bot.on_message(filters=filters.command(['options']))
async def on_options(client: Client, message: Message):
    db = DB()
    user_options = await db.get(MangaOutput, str(message.from_user.id))
    user_options = user_options.output if user_options else (1 << 30) - 4
    buttons = get_buttons_for_options(user_options)
    return await message.reply('Select the desired output format.', reply_markup=buttons)


@bot.on_message(filters=filters.regex(r'^/'))
async def on_unknown_command(client: Client, message: Message):
    await message.reply('Unknown command')


@bot.on_message(filters.create(manga_unique_filter))
async def on_message(client: Client, message: Message):
    manga = mangas[message.text]

    pagination = Pagination()
    paginations[pagination.id] = pagination
    results = await manga.client.get_chapters(manga)
    for result in results:
        chapters[result.unique()] = result
    pagination.chapters = results
    buttons = get_buttons_for_chapters(pagination)

    try:
        message = await bot.send_photo(message.from_user.id,
                                       manga.picture_url,
                                       f'{manga.name}\n'
                                       f'{manga.get_url()}', reply_markup=buttons)
        pagination.message = message
    except pyrogram.errors.BadRequest:
        file_name = f'pictures/{manga.unique()}.jpg'
        await manga.client.get_cover(manga, cache=True, file_name=file_name)
        message = await bot.send_photo(message.from_user.id,
                                       f'./cache/{manga.client.name}/{file_name}',
                                       f'{manga.name}\n'
                                       f'{manga.get_url()}', reply_markup=buttons)
        pagination.message = message


@bot.on_inline_query()
async def on_inline_query(client: Client, inline_query: InlineQuery):
    for ident, manga_client in plugins.items():
        if inline_query.query.startswith(ident):
            query = inline_query.query[len(ident):].strip()

            if not query:
                return await client.answer_inline_query(inline_query.id, results=[])
            results = await manga_client.search(query)
            if not results:
                return await client.answer_inline_query(inline_query.id, results=[])
            for result in results:
                mangas[result.unique()] = result
            return await inline_query.answer(
                results=[
                    InlineQueryResultArticle(
                        title=result.name,
                        thumb_url=result.picture_url,
                        description=result.additional,
                        input_message_content=InputTextMessageContent(result.unique())
                    ) for result in results
                ]
            )


async def search_click(client, callback: CallbackQuery):
    lang = callback.data.split('_')[-1]

    if lang == 'unset':
        return await callback.message.edit('Select search languages.', reply_markup=InlineKeyboardMarkup(
            split_list([InlineKeyboardButton(language, callback_data=f'search_{language}')
                        for language in plugin_dicts.keys()])
        ))
    await callback.message.edit(f'Language: {lang}\n\nSelect search plugin.', reply_markup=InlineKeyboardMarkup(
        split_list([InlineKeyboardButton(ident, switch_inline_query_current_chat=f'[{lang}] {ident} ')
                    for ident in plugin_dicts[lang].keys() if f'[{lang}] {ident}' not in disabled]) + [
            [InlineKeyboardButton('◀️ Back', callback_data=f'search_unset')]]
    ))


async def options_click(client, callback: CallbackQuery):
    db = DB()
    user_options = await db.get(MangaOutput, str(callback.from_user.id))
    if not user_options:
        user_options = MangaOutput(user_id=str(callback.from_user.id), output=(2 << 30) - 4)
    option = int(callback.data.split('_')[-1])
    user_options.output ^= option
    buttons = get_buttons_for_options(user_options.output)
    await db.add(user_options)
    return await callback.message.edit_reply_markup(reply_markup=buttons)


async def chapter_click(client, data, chat_id):
    async with await get_user_lock(chat_id):
        await send_manga_chapter(client, data, chat_id)
        await asyncio.sleep(5)


async def pagination_click(client: Client, callback: CallbackQuery):
    pagination_id, page = map(int, callback.data.split('_'))
    pagination = paginations[pagination_id]
    pagination.page = page

    buttons = get_buttons_for_chapters(pagination)

    await bot.edit_message_reply_markup(
        callback.from_user.id,
        pagination.message.id,
        reply_markup=buttons
    )


async def send_manga_chapter(client, data, chat_id):
    chapter = chapters[data]
    db = DB()

    chapter_file = await db.get(ChapterFile, chapter.url)
    options = await db.get(MangaOutput, str(chat_id))
    options = options.output if options else (1 << 30) - 4

    error_caption = '\n'.join([
        f'{chapter.manga.name} - {chapter.name}',
        f'{chapter.get_url()}'
    ])

    success_caption = f'{chapter.manga.name} - {chapter.name}\n'

    download = not chapter_file
    download = download or options & OutputOptions.PDF and not chapter_file.file_id
    download = download or options & OutputOptions.CBZ and not chapter_file.cbz_id
    download = download or options & OutputOptions.Telegraph and not chapter_file.telegraph_url
    download = download and options & ((1 << len(OutputOptions)) - 1) != 0

    if download:
        pictures_folder = await chapter.client.download_pictures(chapter)
        if not chapter.pictures:
            return await bot.send_message(chat_id,
                                          f'There was an error parsing this chapter or chapter is missing' +
                                          f', please check the chapter at the web\n\n{error_caption}')
        thumb_path = fld2thumb(pictures_folder)

    chapter_file = chapter_file or ChapterFile(url=chapter.url)

    if download and not chapter_file.telegraph_url:
        chapter_file.telegraph_url = await img2tph(chapter, clean(f'{chapter.manga.name} {chapter.name}'))

    if options & OutputOptions.Telegraph:
        success_caption += f'[Read on telegraph]({chapter_file.telegraph_url})\n'
    success_caption += f'[Read on website]({chapter.get_url()})'

    ch_name = clean(f'{clean(chapter.manga.name, 25)} - {chapter.name}', 45)

    media_docs = []

    if options & OutputOptions.PDF:
        if chapter_file.file_id:
            media_docs.append(InputMediaDocument(chapter_file.file_id))
        else:
            try:
                pdf = fld2pdf(pictures_folder, ch_name)
            except Exception as e:
                logger.exception(f'Error creating pdf for {chapter.name} - {chapter.manga.name}\n{e}')
                return await bot.send_message(chat_id, f'There was an error making the pdf for this chapter. '
                                                       f'Forward this message to the bot group to report the '
                                                       f'error.\n\n{error_caption}')
            media_docs.append(InputMediaDocument(pdf, thumb=thumb_path))

    if options & OutputOptions.CBZ:
        if chapter_file.cbz_id:
            media_docs.append(InputMediaDocument(chapter_file.cbz_id))
        else:
            try:
                cbz = fld2cbz(pictures_folder, ch_name)
            except Exception as e:
                logger.exception(f'Error creating cbz for {chapter.name} - {chapter.manga.name}\n{e}')
                return await bot.send_message(chat_id, f'There was an error making the cbz for this chapter. '
                                                       f'Forward this message to the bot group to report the '
                                                       f'error.\n\n{error_caption}')
            media_docs.append(InputMediaDocument(cbz, thumb=thumb_path))

    if len(media_docs) == 0:
        messages: list[Message] = await retry_on_flood(bot.send_message)(chat_id, success_caption)
    else:
        media_docs[-1].caption = success_caption
        messages: list[Message] = await retry_on_flood(bot.send_media_group)(chat_id, media_docs)

    # Save file ids
    if download and media_docs:
        for message in [x for x in messages if x.document]:
            if message.document.file_name.endswith('.pdf'):
                chapter_file.file_id = message.document.file_id
                chapter_file.file_unique_id = message.document.file_unique_id
            elif message.document.file_name.endswith('.cbz'):
                chapter_file.cbz_id = message.document.file_id
                chapter_file.cbz_unique_id = message.document.file_unique_id

    if download:
        shutil.rmtree(pictures_folder, ignore_errors=True)
        await db.add(chapter_file)


def is_pagination_data(callback: CallbackQuery):
    data = callback.data
    match = re.match(r'\d+_\d+', data)
    if not match:
        return False
    pagination_id = int(data.split('_')[0])
    if pagination_id not in paginations:
        return False
    pagination = paginations[pagination_id]
    if not pagination.message:
        return False
    if pagination.message.chat.id != callback.from_user.id:
        return False
    if pagination.message.id != callback.message.id:
        return False
    return True


async def get_user_lock(chat_id: int):
    async with asyncio.Lock():
        lock = locks.get(chat_id)
        if not lock:
            locks[chat_id] = asyncio.Lock()
        return locks[chat_id]


@bot.on_callback_query()
async def on_callback_query(client, callback: CallbackQuery):
    if callback.data in chapters:
        await chapter_click(client, callback.data, callback.from_user.id)
    elif is_pagination_data(callback):
        await pagination_click(client, callback)
    elif callback.data.startswith('search'):
        await search_click(client, callback)
    elif callback.data.startswith('options'):
        await options_click(client, callback)
    else:
        return await bot.answer_callback_query(callback.id, 'This is an old button, please redo the search', show_alert=True)
    try:
        await callback.answer()
    except BaseException as e:
        logger.warning(e)
