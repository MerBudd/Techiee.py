"""
Image processor cog - Handles image attachment processing.
"""
from discord.ext import commands

from utils.helpers import split_and_send_messages
from utils.gemini import process_image_attachment


class ImageProcessor(commands.Cog):
    """Cog for processing image attachments."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, attachment, cleaned_text, settings):
        """Process an image attachment."""
        print(f"New Image Message FROM: {message.author.name} : {cleaned_text}")
        print("Processing Image")
        response_text = await process_image_attachment(attachment, cleaned_text, settings)
        await split_and_send_messages(message, response_text, 1900)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(ImageProcessor(bot))
