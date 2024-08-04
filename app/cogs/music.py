import asyncio
import re
from urllib import response

import discord
import httpx
from discord.ext import commands

from ..video import YTDLSource

url_pattern = r"^(https?://)?(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$"


async def audio_playing(ctx):
    """Checks that audio is currently playing before continuing."""
    client = ctx.guild.voice_client
    if client and client.channel and client.source:
        return True
    else:
        raise commands.CommandError("Not currently playing any audio.")


async def in_voice_channel(ctx):
    """Checks that the command sender is in the same voice channel as the bot."""
    voice = ctx.author.voice
    bot_voice = ctx.guild.voice_client
    if (
        voice
        and bot_voice
        and voice.channel
        and bot_voice.channel
        and voice.channel == bot_voice.channel
    ):
        return True
    else:
        raise commands.CommandError("You need to be in the channel to do that.")


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.now_playing = None

    @commands.hybrid_command(name="join")
    @commands.guild_only()
    async def join(self, ctx):
        """Joins a voice channel"""
        if not ctx.message.author.voice:
            await ctx.send(
                "{} is not connected to a voice channel".format(ctx.message.author.name)
            )
            return
        else:
            channel = ctx.message.author.voice.channel
        await channel.connect()

    @commands.hybrid_command(name="stop")
    @commands.guild_only()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        client = ctx.guild.voice_client
        if client and client.channel:
            await ctx.voice_client.disconnect()
            self.queue = []
            self.now_playing = None
        else:
            raise commands.CommandError("Not in a voice channel.")

    @commands.hybrid_command(name="nowplaying", aliases=["np"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def nowplaying(self, ctx):
        """Displays information about the current song."""
        embed = discord.Embed(color=discord.Color.blurple())
        embed.add_field(
            name=f"Now playing",
            value=f"[{self.now_playing.title}]({self.now_playing.url}) [{ctx.author.mention}]",
        )
        await ctx.send(embed=embed)

    async def _search_yt(self, args):
        params = {"search_query": args}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.youtube.com/results", params=params
            )
            search_results = re.findall(r"/watch\?v=(.{11})", response.text)
            return search_results[0]

    @commands.hybrid_command(name="play", aliases=["p"])
    @commands.guild_only()
    async def play(self, ctx, *, song: str):
        """Streams from a url or a search query (almost anything youtube_dl supports)"""

        if not re.match(url_pattern, song):
            video_id = await self._search_yt(song)
            song = f"https://www.youtube.com/watch?v={video_id}"
            if not video_id:
                await ctx.send("No video IDs found for the search query.")

        client = ctx.guild.voice_client

        if client and client.channel:
            source = await YTDLSource.from_url(song, loop=self.bot.loop, stream=True)
            self.queue.append(source)
            embed = discord.Embed(
                description=f"Queued [{source.title}]({source.url}) [{ctx.author.mention}]",
                color=discord.Color.blurple(),
            )
            await ctx.send(embed=embed)
        else:
            if ctx.author.voice is not None and ctx.author.voice.channel is not None:
                channel = ctx.author.voice.channel
                source = await YTDLSource.from_url(
                    song, loop=self.bot.loop, stream=True
                )
                client = await channel.connect()
                self._play_song(client, source)
                await self.nowplaying(ctx)
            else:
                await ctx.send("You are not connected to a voice channel.")

    def _play_song(self, client, source):
        self.now_playing = source

        def after_playing(error):
            if error:
                print(f"Error after playing a song: {error}")

            if len(self.queue) > 0:
                next_source = self.queue.pop(0)
                asyncio.run_coroutine_threadsafe(
                    self._play_song(client, next_source), self.bot.loop
                )
            else:
                asyncio.run_coroutine_threadsafe(client.disconnect(), self.bot.loop)

        client.play(source, after=after_playing)

    @commands.hybrid_command(name="queue", aliases=["playlist", "q"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def queue(self, ctx):
        """Display the current play queue."""
        message = self._queue_text(self.queue)
        embed = discord.Embed(
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Queue", value=message)
        await ctx.send(embed=embed)

    def _queue_text(self, queue):
        """Returns a block of text describing a given song queue."""
        message = []
        if len(queue) > 0:
            for index, song in enumerate(queue):
                message.append(f"{index+1}) {song.title}")
            return "\n".join(message)
        else:
            return "The queue is empty!"

    @commands.hybrid_command(name="clear")
    @commands.guild_only()
    @commands.check(audio_playing)
    async def clear_queue(self, ctx):
        """Clears the play queue without leaving the channel."""
        self.queue = []

    @commands.hybrid_command(name="volume", aliases=["vol", "v"])
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.check(in_voice_channel)
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        embed = discord.Embed(
            description=f"Changed volume to {volume}% [{ctx.author.mention}]",
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pause", aliases=["resume"])
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.check(in_voice_channel)
    async def pause(self, ctx):
        client = ctx.guild.voice_client
        if client.is_paused():
            client.resume()
        else:
            client.pause()

    @commands.hybrid_command(name="skip")
    @commands.guild_only()
    @commands.check(audio_playing)
    @commands.check(in_voice_channel)
    async def skip(self, ctx):
        client = ctx.voice_client
        client.stop()

    @commands.hybrid_command(name="searchwaifu")
    async def randomwaifu(self, ctx, tags: str = None):
        url = 'https://api.waifu.im/search'
        
        # Si no se proporcionan tags, usa un conjunto predeterminado
        included_tags = tags.split(",") if tags else ['raiden-shogun', 'maid']
        
        params = {
            'included_tags': included_tags,
            'height': '>=2000'
        }

        async with httpx.AsyncClient() as client:
         response = await client.get(url, params=params)
         if response.status_code == 200:
            data = response.json()
            
            # imprimiendo datos
            print(data)
            
            images = data.get("images", [])
            if images:
                image = images[0]
                image_url = image.get("url")  # Asegúrate de que este es el campo correcto
                
                if image_url:
                    # Envía el mensaje con la imagen
                    embed = discord.Embed(title="Onichan /ᐠ - ˕ -マ")
                    embed.set_image(url=image_url)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("No hay URL de imagen en la respuesta.")
            else:
                await ctx.send("No hay resultados para el tag")
         else:
            await ctx.send(f"API returned a {response.status_code} status code")

    @commands.hybrid_command(name="waifulist")
    async def waifulist(self, ctx):
        URL = "https://api.waifu.im/tags"
        async with httpx.AsyncClient() as client:
            response = await client.get(URL)
        
        if response.status_code == 200:
            data = response.json()
            versatile_tags = data.get("versatile", [])
            nsfw_tags = data.get("nsfw", [])
            
            # Construir el mensaje
            message = "Lista de waifus:\n"
            message += "Versatile:\n" + "\n".join(f"- {tag}" for tag in versatile_tags) + "\n\n"
            message += "NSFW:\n" + "\n".join(f"- {tag}" for tag in nsfw_tags)

            await ctx.send(message)
        else:
            await ctx.send(f"API returned a {response.status_code} status code")


    @commands.hybrid_command(name="startserver")
    async def startserver(self, ctx):
        URL = "https://2sisz7vc3f.execute-api.us-east-1.amazonaws.com/prod/v1/launch"
        
        # Leer el contenido del archivo de texto
        with open('public/ascii.txt', 'r') as file:
            ascii_art = file.read()
        
        while True:
            async with httpx.AsyncClient() as client:
                response = await client.get(URL)
                if response.status_code == 200:
                    data = response.json()
                    message = data.get("message")
                    sfn_execution_in_progress = data.get("sfn_execution_in_progress", "false").strip().lower()
                    server_status = data.get("server_status", "false").strip().lower()

                    # Construyendo el mensaje
                    response_message = f"Server started:\n- {message}\n- sfn_execution_in_progress: {sfn_execution_in_progress}"

                    if server_status == "true":
                        await ctx.send(f"Server start successful\nIP: pz-craft.online\n```\n{ascii_art}\n```")
                        break
                    else:
                        await ctx.send(f"{response_message}\nRetrying...\n```\n{ascii_art}\n```")
                        await asyncio.sleep(120)  # Esperar 2 minutos antes de volver a intentar
                elif response.status_code == 202:
                    await ctx.send(f"API returned a {response.status_code} status code. Retrying...")
    

    @commands.hybrid_command(name="serverstatus")
    async def serverstatus(self, ctx):
        URL = "https://api.mcsrvstat.us/3/pz-craft.online"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(URL)
            if response.status_code == 200:
                data = response.json()
                
                # Crear un embed para mostrar la información del servidor
                embed = discord.Embed(title="PZ MINECRAFT SERVER", color=discord.Color.green() if data['online'] else discord.Color.red())
                embed.add_field(name="IP", value=data['ip'], inline=True)
                embed.add_field(name="Port", value=data['port'], inline=True)
                embed.add_field(name="Version", value=data['version'], inline=True)
                embed.add_field(name="Players Online", value=f"{data['players']['online']}/{data['players']['max']}", inline=True)
                embed.add_field(name="MOTD", value=' '.join(data['motd']['clean']), inline=False)
                
                # Lista de jugadores
                if data['players']['online'] > 0:
                    for player in data['players']['list']:
                        player_name = player['name']
                        player_avatar_url = f"https://mineskin.eu/avatar/{player_name}"
                        embed.add_field(name="Player", value=f"{player_name}\n[Avatar]({player_avatar_url})", inline=True)
                        embed.set_image(url=player_avatar_url)
                
                class InvokeCommandButton(discord.ui.View):
                    @discord.ui.button(label="Start Server", style=discord.ButtonStyle.green)
                    async def invoke_command(self, button: discord.ui.Button, interaction: discord.Interaction):
                        # Defer the interaction response to acknowledge the button press
                        await interaction.response.defer()
                        # Llamar al método startserver directamente
                        await self.startserver(interaction.channel)

                view = InvokeCommandButton()
                await ctx.send(embed=embed, view=view)
            else:
                await ctx.send(f"Failed to retrieve server status. Status code: {response.status_code}")