import re

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, \
    InlineQueryResultArticle, InputTextMessageContent

from bot import Bot, clients_dicts, disabled, clients, split_list, mangas


@Bot.on_message(filters.command(['search']))
async def on_search(client: Bot, message: Message):
    await message.reply('Select search languages.', reply_markup=InlineKeyboardMarkup(
        split_list([InlineKeyboardButton(language, callback_data=f'search_{language}')
                    for language in clients_dicts.keys()])
    ))


@Bot.on_callback_query(filters.regex(r'^search_'))
async def on_callback_query(client: Bot, callback: CallbackQuery):
    lang = callback.data.split('_')[-1]

    if lang == 'unset':
        await callback.message.edit('Select search languages.', reply_markup=InlineKeyboardMarkup(
            split_list([InlineKeyboardButton(language, callback_data=f'search_{language}')
                        for language in clients_dicts.keys()])
        ))
        return
    await callback.message.edit(f'Language: {lang}\n\nSelect search plugin.', reply_markup=InlineKeyboardMarkup(
        split_list([InlineKeyboardButton(ident, switch_inline_query_current_chat=f'[{lang}] {ident} ')
                    for ident in clients_dicts[lang].keys() if f'[{lang}] {ident}' not in disabled]) + [
            [InlineKeyboardButton('◀️ Back', callback_data=f'search_unset')]]
    ))


@Bot.on_inline_query(filters.regex(rf'^({"|".join(map(re.escape, clients.keys()))})'))
async def on_inline_query(client: Bot, inline_query: InlineQuery):
    for ident, manga_client in clients.items():
        if inline_query.query.startswith(ident):
            query = inline_query.query[len(ident):].strip()
            if not query:
                await inline_query.answer([])
                return
            results = await manga_client.search(query)
            if not results:
                await inline_query.answer([])
                return
            for result in results:
                mangas[result.unique()] = result
            await inline_query.answer(
                [
                    InlineQueryResultArticle(
                        title=result.name,
                        thumb_url=result.picture_url,
                        description=result.additional,
                        input_message_content=InputTextMessageContent(result.unique()),
                    ) for result in results
                ],
                cache_time=0
            )
            return
