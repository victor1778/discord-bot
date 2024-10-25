import asyncio
import signal
import sys
from os import getenv
from typing import Optional

from dotenv import load_dotenv

from src.bot import Bot
from src.utils.logger import logger

# Load environment variables
load_dotenv()

# Get configuration
TOKEN = getenv("TOKEN")
if not TOKEN:
    logger.critical("No TOKEN found in environment variables")
    sys.exit(1)

# Initialize bot
bot = Bot()


async def shutdown(signal: Optional[signal.Signals] = None):
    """
    Cleanly shut down the bot and close all connections.
    """
    if signal:
        logger.info(f"Received exit signal {signal.name}...")

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]

    logger.info(f"Cancelling {len(tasks)} outstanding tasks...")
    await asyncio.gather(*tasks, return_exceptions=True)
    await bot.close()

    logger.info("Bot shutdown complete.")


def handle_exception(loop, context):
    """Handle exceptions that escape the event loop."""
    msg = context.get("exception", context["message"])
    logger.error(f"Caught exception: {msg}")
    asyncio.create_task(shutdown())


async def main():
    """Main entry point for the bot."""
    try:
        # Set up signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))

        # Set up exception handler
        loop.set_exception_handler(handle_exception)

        logger.info("Starting bot...")
        await bot.start(TOKEN)

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        await shutdown()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    finally:
        logger.info("Program ended.")
