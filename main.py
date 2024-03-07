import asyncio as aio

from bot import bot
from models import DB
from tools.updater import manga_updater


async def async_main():
    db = DB()
    await db.connect()

if __name__ == '__main__':
    loop = aio.get_event_loop_policy().get_event_loop()
    loop.run_until_complete(async_main())
    loop.create_task(manga_updater())
    bot.run()
