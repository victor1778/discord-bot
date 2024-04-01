import asyncio
import os

import discord
from dotenv import load_dotenv

from app.bot import Bot
from app.cogs import Music

if not discord.opus.is_loaded():
    discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

bot = Bot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


async def setup():
    await bot.add_cog(Music(bot))
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(setup())
