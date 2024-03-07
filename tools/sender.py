import shutil

from loguru import logger
from pyrogram.types import InputMediaDocument, InlineKeyboardMarkup, InlineKeyboardButton, Message

from bot import Bot, chapters
from clients.client import clean
from img2pdf.core import fld2thumb, fld2pdf
from img2tph.core import img2tph
from models import DB, ChapterFile
from models.db import MangaOutput
from output_options import OutputOptions
from pagination import Pagination
from tools.flood import retry_on_flood


async def send_manga_chapter(client: Bot, data, chat_id: int):
    chapter = chapters[data]
    db = DB()

    chapter_file = await db.get(ChapterFile, chapter.url)
    options = await db.get(MangaOutput, str(chat_id))
    options = options.output if options else (1 << 30) - 7

    error_caption = '\n'.join([
        f'{chapter.manga.name} - {chapter.name}',
        f'{chapter.get_url()}'
    ])

    success_caption = f'{chapter.manga.name} - {chapter.name}\n'

    download = not chapter_file
    download = download or options & OutputOptions.PDF and not chapter_file.file_id
    download = download or options & OutputOptions.Telegraph and not chapter_file.telegraph_url
    download = download and options & ((1 << len(OutputOptions)) - 1) != 0

    if download:
        pictures_folder = await chapter.client.download_pictures(chapter)
        if not chapter.pictures:
            return await client.send_message(chat_id, f'There was an error parsing this chapter or chapter is missing' +
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
                return await client.send_message(chat_id, f'There was an error making the pdf for this chapter. '
                                                          f'Forward this message to the bot group to report the '
                                                          f'error.\n\n{error_caption}')
            media_docs.append(InputMediaDocument(pdf, thumb=thumb_path))

    pagination = Pagination()
    pagination.chapters = chapter.manga.chapters
    footer = []
    prev = pagination.get_prev_chapter(chapter)
    next_ = pagination.get_next_chapter(chapter)
    if next_:
        footer.append(InlineKeyboardButton('Previous Chapter', next_.unique()))
    if prev:
        footer.append(InlineKeyboardButton('Next Chapter', prev.unique()))

    if len(media_docs) == 0:
        message = await retry_on_flood(client.send_message)(
            chat_id,
            success_caption
        )
        messages: list[Message] = [message]
    else:
        media_docs[-1].caption = success_caption
        messages: list[Message] = await retry_on_flood(client.send_media_group)(
            chat_id,
            media_docs
        )

    if len(footer) != 0:
        await retry_on_flood(client.edit_message_reply_markup)(
            chat_id,
            messages[-1].id,
            reply_markup=InlineKeyboardMarkup([footer])
        )

    # Save file ids
    if download and media_docs:
        for message in [x for x in messages if x.document]:
            if message.document.file_name.endswith('.pdf'):
                chapter_file.file_id = message.document.file_id
                chapter_file.file_unique_id = message.document.file_unique_id

    if download:
        shutil.rmtree(pictures_folder, ignore_errors=True)
        await db.add(chapter_file)
