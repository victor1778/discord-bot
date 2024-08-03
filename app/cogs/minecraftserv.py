import discord
from discord.ext import commands
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL")
API_TOKEN = os.getenv("API_TOKEN")

class Server(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="startserver")
    @commands.guild_only()
    async def start_server(self, ctx):
        """Starts the server by sending a POST request to the API"""

        headers = {
            'Authorization': f'Bearer {API_TOKEN}',
            'Content-Type': 'application/json',
        }

        payload = {
            # Añade aquí los datos necesarios para tu API
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(API_URL, json=payload, headers=headers)
                if response.status_code == 200:
                    await ctx.send("Server started successfully!")
                else:
                    await ctx.send(f"Failed to start server: {response.status_code} {response.text}")
            except Exception as e:
                await ctx.send(f"An error occurred: {str(e)}")

def setup(bot):
    bot.add_cog(Server(bot))