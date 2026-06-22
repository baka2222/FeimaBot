import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.bot import bot
from bot.handlers import auth, searchman, ai_creator

logging.basicConfig(level=logging.INFO)


async def main():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(auth.router)
    dp.include_router(searchman.router)
    dp.include_router(ai_creator.router)

    await dp.start_polling(bot, skip_updates=True)


if __name__ == '__main__':
    asyncio.run(main())
