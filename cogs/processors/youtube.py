"""
YouTube processor cog - Handles YouTube URL processing.
"""
from discord.ext import commands

from utils.helpers import split_and_send_messages
from utils.gemini import process_youtube_url


class YouTubeProcessor(commands.Cog):
    """Cog for processing YouTube URLs."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, url, cleaned_text, settings):
        """Process a YouTube URL."""
        print(f"New YouTube URL FROM: {message.author.name} : {url}")
        print("Processing YouTube Video")
        response_text = await process_youtube_url(url, cleaned_text, settings)
        await split_and_send_messages(message, response_text, 1900)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(YouTubeProcessor(bot))
