import discord
from discord.ext import commands
import os
import sys

from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print("Bot ready")
    # Finding a channel to read from, maybe just wait for a message
    print("Please send a Tenor GIF link in any channel the bot can see.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.embeds:
        for i, embed in enumerate(message.embeds):
            print(f"Embed {i}: type={embed.type}, provider={embed.provider.name if embed.provider else None}")
            print(f"  url: {embed.url}")
            if embed.thumbnail:
                print(f"  thumbnail.url: {embed.thumbnail.url}")
                print(f"  thumbnail.proxy_url: {embed.thumbnail.proxy_url}")
            if embed.video:
                print(f"  video.url: {embed.video.url}")
                print(f"  video.proxy_url: {embed.video.proxy_url}")
            if embed.image:
                print(f"  image.url: {embed.image.url}")
                print(f"  image.proxy_url: {embed.image.proxy_url}")
        
        await bot.close()

bot.run(TOKEN)
