"""
Website processor cog - Handles website URL processing.
"""
from discord.ext import commands

from utils.helpers import split_and_send_messages
from utils.gemini import process_website_url


class WebsiteProcessor(commands.Cog):
    """Cog for processing website URLs."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, url, cleaned_text, settings):
        """Process a website URL."""
        print(f"New Website URL FROM: {message.author.name} : {url}")
        print("Processing Website URL")
        response_text = await process_website_url(url, cleaned_text, settings)
        await split_and_send_messages(message, response_text, 1900)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(WebsiteProcessor(bot))
