from asyncio import run
from os import getenv

from dotenv import load_dotenv

from src.bot import Bot

load_dotenv()

TOKEN = getenv("TOKEN")
bot = Bot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


async def main():
    await bot.start(TOKEN)


if __name__ == "__main__":
    run(main())
