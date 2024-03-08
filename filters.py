from pyrogram.filters import create
from pyrogram.types import Update, Message, CallbackQuery, InlineQuery

from bot import mangas, chapters


def manga(prefix: str = None):
    async def func(flt, _, update: Update):
        if isinstance(update, Message):
            value = update.text or update.caption
        elif isinstance(update, CallbackQuery):
            value = update.data
        elif isinstance(update, InlineQuery):
            value = update.query
        else:
            raise ValueError(f"Manga filter doesn't work with {type(update)}")

        if not value:
            return False


        if not flt.p:
            basis = value
        else:
            if not value.startswith(flt.p):
                return False
            basis = value[len(flt.p):]

        unique = basis.split('_')[0]

        return unique in mangas

    return create(
        func,
        "MangaFilter",
        p=prefix
    )


def chapter(prefix: str = None):
    async def func(flt, _, update: Update):
        if isinstance(update, Message):
            value = update.text or update.caption
        elif isinstance(update, CallbackQuery):
            value = update.data
        elif isinstance(update, InlineQuery):
            value = update.query
        else:
            raise ValueError(f"Chapter filter doesn't work with {type(update)}")

        if not value:
            return False

        if not flt.p:
            basis = value
        else:
            if not value.startswith(flt.p):
                return False
            basis = value[len(flt.p):]

        unique = basis.split('_')[0]

        return unique in chapters

    return create(
        func,
        "ChapterFilter",
        p=prefix
    )

