"""Bot entry point: initialization and startup."""

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.config import BOT_TOKEN, ADMIN_IDS, DATA_DIR
from app.phrases import load_phrases, get_system
from app.db import init_db
from app.handlers import common, survey, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Load phrases
    load_phrases()

    # Initialize database
    await init_db()

    # Create bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

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

    logger.info("Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
