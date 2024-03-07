from datetime import datetime
from typing import Dict

from loguru import logger
from pyrogram import Client

from config import env_vars, dbname
from models import DB
from clients import MangaCard, MangaChapter, MangaClient, MintMangaClient, ReadMangaClient

clients_dicts: Dict[str, Dict[str, MangaClient]] = {
    '🇷🇺 RU': {
        'ReadManga': ReadMangaClient(),
        'MintManga': MintMangaClient()
    }
}

disabled = []

subsPaused = disabled + []

clients = dict()
for lang, clients_dict in clients_dicts.items():
    for name, client in clients_dict.items():
        identifier = f'[{lang}] {name}'
        if identifier in disabled:
            continue
        clients[identifier] = client

mangas: Dict[str, MangaCard] = dict()
chapters: Dict[str, MangaChapter] = dict()
users_in_channel: Dict[int, datetime] = dict()


class Bot(Client):
    def __init__(self):
        super().__init__(
            name='Bot',
            api_id=env_vars.get('API_ID'),
            api_hash=env_vars.get('API_HASH'),
            bot_token=env_vars.get('BOT_TOKEN'),
            max_concurrent_transmissions=3,
            plugins={'root': 'plugins'}
        )

    async def start(self):
        await super().start()
        logger.info("Bot started.")

    async def stop(self, *args):
        await super().stop()
        logger.info("Bot stopped.")


bot = Bot()

if dbname:
    DB(dbname)
else:
    DB()


def split_list(li):
    return [li[x: x + 2] for x in range(0, len(li), 2)]
