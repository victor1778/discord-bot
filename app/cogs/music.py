import asyncio
import re
import random
from urllib import response

import discord
import httpx
from discord.ext import commands
import os

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
        """Searching waifu"""
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
        """Use to get a list of waifus"""
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
        """Use to initialize the PZ SERVER"""
        print("Command startserver invoked")  # Log inicial
        URL = "https://bio43yhumd.execute-api.us-east-1.amazonaws.com/prod/v1/server/start"
        async with httpx.AsyncClient() as client:
            response = await client.get(URL)
            print(f"Received response with status code: {response.status_code}")  # Log de la respuesta

            # Construir la respuesta
            data = response.json()
            success = data.get("success", "false").strip().lower()
            server_status = data.get("server_status", "UNKNOWN").strip().upper()

            embed = discord.Embed(title="INITIALIZING SERVER", color=discord.Color.greyple())

            # Añadir la imagen local al embed
            gif_path = 'public/images/Enchanting_Table.gif'  # Ruta relativa a la imagen
            file = None
            if os.path.exists(gif_path):
                print(f"Image found at path: {gif_path}")  # Log de la imagen encontrada
                with open(gif_path, 'rb') as image_file:
                    file = discord.File(image_file, filename='Enchanting_Table.gif')
                    embed.set_image(url="attachment://Enchanting_Table.gif")
            else:
                print(f"Image not found at path: {gif_path}")  # Log de la imagen no encontrada

            if success == "true":
                print("Server start successful")  # Log del inicio del servidor
                embed.add_field(name="Server Start", value="Server start successful")
                embed.add_field(name="IP", value="pz-craft.online")
                embed.add_field(name="STATUS", value=server_status)
            else:
                print(f"Unexpected response: {data}")  # Log de una respuesta inesperada
                embed.add_field(name="Error", value="Failed to start server")
                embed.add_field(name="STATUS", value="Check server logs")

            # Enviar el embed con el archivo si existe
            if file:
                print("Sending embed with file")  # Log del envío del embed con archivo
                await ctx.send(embed=embed, file=file)
            else:
                print("Sending embed without file")  # Log del envío del embed sin archivo
                await ctx.send(embed=embed)

    
    @commands.hybrid_command(name="stopserver")
    async def stopserver(self, ctx):
        """Use to stop the PZ SERVER"""
        print("Command stopserver invoked")  # Log inicial
        URL = "https://bio43yhumd.execute-api.us-east-1.amazonaws.com/prod/v1/server/stop"
        async with httpx.AsyncClient() as client:
            response = await client.get(URL)
            print(f"Received response with status code: {response.status_code}")  # Log de la respuesta

        # Construir la respuesta
        data = response.json()
        success = data.get("success", "false").strip().lower()
        server_status = data.get("server_status", "UNKNOWN").strip().upper()

        embed = discord.Embed(title="STOPPING SERVER", color=discord.Color.red())

        # Añadir la imagen local al embed
        tnt_path = 'public/images/tnt.png'  # Ruta relativa a la imagen
        file = None
        if os.path.exists(tnt_path):
            print(f"Image found at path: {tnt_path}")  # Log de la imagen encontrada
            with open(tnt_path, 'rb') as image_file:
                file = discord.File(image_file, filename='tnt.png')
                embed.set_image(url="attachment://tnt.png")
        else:
            print(f"Image not found at path: {tnt_path}")  # Log de la imagen no encontrada

        if success == "true":
            print("Server stop initiated")  # Log del inicio de la parada del servidor
            embed.add_field(name="Server Stop", value="Server stop successful")
            embed.add_field(name="IP", value="pz-craft.online")
            embed.add_field(name="STATUS", value=server_status)
        elif success == "false":
            print(f"Unexpected response: {data}")  # Log de una respuesta inesperada
            embed.add_field(name="Status", value="off")
            embed.add_field(name="Information", value=server_status)

        # Enviar el embed con el archivo si existe
        if file:
            print("Sending embed with file")  # Log del envío del embed con archivo
            await ctx.send(embed=embed, file=file)
        else:
            print("Sending embed without file")  # Log del envío del embed sin archivo
            await ctx.send(embed=embed)
    

    @commands.hybrid_command(name="serverstadistics")
    async def serverstatus(self, ctx):
        """Check if server status and refresh every 10 minutes"""
        URL = "https://api.mcsrvstat.us/3/pz-craft.online"
        async with httpx.AsyncClient() as client:
                response = await client.get(URL)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Crear un embed para mostrar la información del servidor
                    embed = discord.Embed(title="PZ MINECRAFT SERVER", color=discord.Color.green() if data['online'] else discord.Color.red())
                    embed.add_field(name="IP", value=data['hostname'], inline=True)
                    embed.add_field(name="Port", value=data['port'], inline=True)
                    embed.add_field(name="Version", value=data['version'], inline=True)
                    embed.add_field(name="Players Online", value=f"{data['players']['online']}/{data['players']['max']}", inline=True)
                    embed.add_field(name="MOTD", value=' '.join(data['motd']['clean']), inline=False)

                    # Añadir la imagen local al embed
                    gif_path = 'public/images/netherportal.gif'  # Ruta relativa a la imagen
                    if os.path.exists(gif_path):
                        with open(gif_path, 'rb') as image_file:
                            file = discord.File(image_file, filename='netherportal.gif')
                            embed.set_image(url="attachment://netherportal.gif")

                    # Lista de jugadores
                    if data['players']['online'] > 0:
                        for player in data['players']['list']:
                            player_name = player['name']
                            player_avatar_url = f"https://mineskin.eu/avatar/{player_name}"
                            embed.add_field(name="Player", value=f"{player_name}\n[Avatar]({player_avatar_url})", inline=True)

                    # Enviar el mensaje inicial y guardar el ID del mensaje
                    if 'message' not in locals():
                        message = await ctx.send(embed=embed, file=file)
                    else:
                        # Editar el mensaje existente
                        await message.edit(embed=embed, attachments=[file])

                else:
                    await ctx.send(f"Failed to retrieve server status. Status code: {response.status_code}")

            # Esperar 10 minutos (1800 segundos) antes de volver a actualizar
        await asyncio.sleep(600)

        self.frecuencia_frases = {
            "tu mama": 0, "me vale mierda": 0, "no me interesa": 0, "mamala hpta": 0, "njds hpta, hpta njds": 0,
            "No me interesan tus problemas": 0, "aja": 0, "que cagada loco": 0, "no solo eso, sos imbecil": 0,
            "pues que patetico": 0, "Me meto en un round": 0, "Es una curva de aprendizaje alta": 0,
            "No julio estás confundido": 0, "Nvm si son más estúpidos de lo que pensaba": 0, "Y los ingenieros?": 0,
            "hay que leer un poco": 0, "Que si tío, que si": 0, "No hombre pero si se parece al de la uam": 0,
            "Si les interesa lo pueden reparar": 0, "Te la debo pipi": 0, "dejame ver si te resuelvo balazo aca": 0,
            "Efectivo hermano": 0, "Así parece": 0, "y que esperas?": 0, "you got me there": 0,
            "i got shit on my ass": 0, "acabe con el racismo": 0, "Njds si Cristian le pusiera esas mismas ganas a la ingeniera real": 0,
            "Que pendejo": 0, "Sheesh?": 0, "el tu mama": 0, "a tu mamita": 0, "veni callame": 0, "Basado": 0,
            "Después apareces en todos los grupos de venta": 0, "F por Joshua": 0, "Pene?": 0,
            "Porque ya no hablas conmigo?": 0, "No chambeaste?": 0, "Y si mejor me la chupas?": 0,
            "Y no podes buscarlo vos?": 0, "me siento solo en esta noche especial": 0,
            "julio no está haciendo nada de seguro": 0, "Sos autista": 0
        }

    @commands.hybrid_command(name="holavictor")
    async def serverstatus(self, ctx):
        """Victor te saluda"""
        frases = [
         "tu mama",
         "me vale mierda",
         "no me interesa",
         "mamala hpta",
         "njds hpta, hpta njds",
         "No me interesan tus problemas",
         "aja",
         "que cagada loco",
         "no solo eso, sos imbecil",
         "pues que patetico",
         "Me meto en un round",
         "Es una curva de aprendizaje alta",
         "No julio estás confundido",
         "Nvm si son más estúpidos de lo que pensaba",
         "Y los ingenieros?",
         "hay que leer un poco",
         "Que si tío, que si",
         "No hombre pero si se parece al de la uam",
         "Si les interesa lo pueden reparar",
         "Te la debo pipi",
         "dejame ver si te resuelvo balazo aca",
         "Efectivo hermano",
         "Así parece",
         "y que esperas?",
         "you got me there",
         "i got shit on my ass",
         "acabe con el racismo",
         "Njds si Cristian le pusiera esas mismas ganas a la ingeniera real",
         "Que pendejo",
         "Sheesh?",
         "tu mamita",
         "a tu mamita",
         "veni callame",
         "Basado",
         "Después apareces en todos los grupos de venta",
         "F por Joshua",
         "Pene?",
         "Porque ya no hablas conmigo?",
         "No chambeaste?",
         "Y si mejor me la chupas?",
         "Y no podes buscarlo vos?",
         "me siento solo en esta noche especial",
         "julio no está haciendo nada de seguro",
         "Sos autista",
         "Julio pero yo te amo"
         ] 
         # Seleccionar una frase aleatoria
        frase_aleatoria = random.choice(frases)
    
         # Crear un embed
        embed = discord.Embed(title="Te saludo amablemente", color=discord.Color.blue())
        embed.add_field(name="Respuesta", value=frase_aleatoria, inline=False)
    
        # Añadir la imagen local al embed si existe
        jpg_path = 'public/images/victor.jpg'  # Ruta relativa a la imagen
        if os.path.exists(jpg_path):
          with open(jpg_path, 'rb') as image_file:
            file = discord.File(image_file, filename='victor.jpg')
            embed.set_image(url="attachment://victor.jpg")
        # Enviar el embed con el archivo
            await ctx.send(embed=embed, file=file)
        else:
          # Enviar el embed sin el archivo si la imagen no existe
          await ctx.send(embed=embed)