"""Bot entry point: initialization and startup."""

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Message, ErrorEvent
from aiogram.fsm.context import FSMContext

from app.config import BOT_TOKEN, ADMIN_IDS, DATA_DIR, REDIS_URL
from app.phrases import load_phrases, get_system
from app.db import init_db
from app.storage import cleanup_tmp
from app import timeouts
from app.handlers import common, survey, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # Ensure data directory exists and clear any temp leftovers from a crash.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_tmp()

    # Load phrases
    load_phrases()

    # Initialize database
    await init_db()

    # Create bot and dispatcher (Redis-backed FSM survives restarts)
    bot = Bot(token=BOT_TOKEN)
    storage = RedisStorage.from_url(REDIS_URL)
    dp = Dispatcher(storage=storage)

    # Inactivity timeouts (Redis-backed sweeper — survives restarts)
    timeouts.manager = timeouts.TimeoutManager(bot, storage, storage.redis)

    # Register routers (order matters!)
    # 1. Common (handles /start — highest priority)
    dp.include_router(common.router)
    # 2. Admin (handles admin-specific messages)
    dp.include_router(admin.router)
    # 3. Survey (handles survey states)
    dp.include_router(survey.router)

    # 4. Fallback router (last — catches out-of-session messages)
    fallback_router = Router()

    @fallback_router.message()
    async def fallback_handler(message: Message, state: FSMContext) -> None:
        """Handle messages from users not in a survey session."""
        if message.from_user.id in ADMIN_IDS:
            return
        await message.answer(get_system("out_of_session"))

    dp.include_router(fallback_router)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        """Log any unhandled exception so one bad update can't crash the bot."""
        logger.exception("Unhandled update error", exc_info=event.exception)
        return True  # mark as handled

    logger.info("Bot starting...")
    timeouts.manager.start()
    try:
        await dp.start_polling(bot)
    finally:
        await timeouts.manager.stop()
        await storage.close()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
