import discord
import lavalink
from discord.ext import commands

from src.cogs import Music

MY_GUILD = discord.Object(id=713553988359946250)


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        # Initialize Lavalink after the bot logs in
        self.lavalink = lavalink.Client(self.user.id)
        self.lavalink.add_node(
            host="34.227.108.209",
            port=2333,
            password="youshallnotpass",
            region="us",
            name="default-node",
        )
        await self.add_cog(Music(self))  # Add the Music cog here
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"Synced slash commands for {self.user}.")
