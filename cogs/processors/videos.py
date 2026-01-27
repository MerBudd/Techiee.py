"""
Video processor cog - Handles video attachment processing.
"""
from discord.ext import commands

from utils.helpers import split_and_send_messages
from utils.gemini import process_video_attachment


class VideoProcessor(commands.Cog):
    """Cog for processing video attachments."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, attachment, cleaned_text, settings):
        """Process a video attachment."""
        print(f"New Video Message FROM: {message.author.name} : {cleaned_text}")
        print("Processing Video")
        response_text = await process_video_attachment(attachment, cleaned_text, settings)
        await split_and_send_messages(message, response_text, 1900)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(VideoProcessor(bot))
