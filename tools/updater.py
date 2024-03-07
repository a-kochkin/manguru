import asyncio
from datetime import datetime, timedelta
from typing import List

from loguru import logger
from pyrogram.errors import UserIsBlocked

from bot import clients, subsPaused, chapters, bot
from clients import MangaChapter
from models import Subscription, LastChapter, MangaName, DB
from tools.sender import send_manga_chapter


async def update_mangas():
    logger.debug("Updating mangas")
    db = DB()
    subscriptions = await db.get_all(Subscription)
    last_chapters = await db.get_all(LastChapter)
    manga_names = await db.get_all(MangaName)

    subs_dictionary = dict()
    chapters_dictionary = dict()
    url_client_dictionary = dict()
    client_url_dictionary = {client: set() for client in clients.values()}
    manga_dict = dict()

    for subscription in subscriptions:
        if subscription.url not in subs_dictionary:
            subs_dictionary[subscription.url] = []
        subs_dictionary[subscription.url].append(subscription.user_id)

    for last_chapter in last_chapters:
        chapters_dictionary[last_chapter.url] = last_chapter

    for manga in manga_names:
        manga_dict[manga.url] = manga

    for url in subs_dictionary:
        for ident, client in clients.items():
            if ident in subsPaused:
                continue
            if await client.contains_url(url):
                url_client_dictionary[url] = client
                client_url_dictionary[client].add(url)

    for client, urls in client_url_dictionary.items():
        logger.debug(f'Updating {client.name}')
        logger.debug(f'Urls:\t{list(urls)}')
        new_urls = [url for url in urls if not chapters_dictionary.get(url)]
        logger.debug(f'New Urls:\t{new_urls}')
        to_check = [chapters_dictionary[url] for url in urls if chapters_dictionary.get(url)]
        if len(to_check) == 0:
            continue
        try:
            updated, not_updated = await client.check_updated_urls(to_check)
        except BaseException as e:
            logger.exception(f"Error while checking updates for site: {client.name}, err: {e}")
            updated = []
            not_updated = list(urls)
        for url in not_updated:
            del url_client_dictionary[url]
        logger.debug(f'Updated:\t{list(updated)}')
        logger.debug(f'Not Updated:\t{list(not_updated)}')

    updated = dict()

    for url, client in url_client_dictionary.items():
        try:
            if url not in manga_dict:
                continue
            manga_name = manga_dict[url].name
            if url not in chapters_dictionary:
                agen = client.iter_chapters(url, manga_name)
                last_chapter = await anext(agen)
                await db.add(LastChapter(url=url, chapter_url=last_chapter.url))
                await asyncio.sleep(10)
            else:
                last_chapter = chapters_dictionary[url]
                new_chapters: List[MangaChapter] = []
                counter = 0
                async for chapter in client.iter_chapters(url, manga_name):
                    if chapter.url == last_chapter.chapter_url:
                        break
                    new_chapters.append(chapter)
                    counter += 1
                    if counter == 20:
                        break
                if new_chapters:
                    last_chapter.chapter_url = new_chapters[0].url
                    await db.add(last_chapter)
                    updated[url] = list(reversed(new_chapters))
                    for chapter in new_chapters:
                        if chapter.unique() not in chapters:
                            chapters[chapter.unique()] = chapter
                await asyncio.sleep(1)
        except BaseException as e:
            logger.exception(f'An exception occurred getting new chapters for url {url}: {e}')

    blocked = set()
    for url, chapter_list in updated.items():
        for chapter in chapter_list:
            logger.debug(f'Updating {chapter.manga.name} - {chapter.name}')
            for sub in subs_dictionary[url]:
                if sub in blocked:
                    continue
                try:
                    await send_manga_chapter(bot, chapter.unique(), int(sub))
                except UserIsBlocked:
                    logger.info(f'User {sub} blocked the bot')
                    await remove_subscriptions(sub)
                    blocked.add(sub)
                except BaseException as e:
                    logger.exception(f'An exception occurred sending new chapter: {e}')
                await asyncio.sleep(0.5)
            await asyncio.sleep(1)


async def manga_updater():
    minutes = 5
    while True:
        wait_time = minutes * 60
        try:
            start = datetime.now()
            await update_mangas()
            elapsed = datetime.now() - start
            wait_time = max((timedelta(seconds=wait_time) - elapsed).total_seconds(), 0)
            logger.debug(f'Time elapsed updating mangas: {elapsed}, waiting for {wait_time}')
        except BaseException as e:
            logger.exception(f'An exception occurred during chapters update: {e}')
        if wait_time:
            await asyncio.sleep(wait_time)


async def remove_subscriptions(sub: str):
    db = DB()

    await db.erase_subs(sub)
