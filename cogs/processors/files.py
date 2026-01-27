"""
File processor cog - Handles PDF and text file attachment processing.
"""
from discord.ext import commands

from utils.helpers import split_and_send_messages
from utils.gemini import process_file_attachment


class FileProcessor(commands.Cog):
    """Cog for processing PDF and text file attachments."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, attachment, cleaned_text, settings):
        """Process a PDF or text file attachment."""
        file_type = 'PDF' if attachment.filename.lower().endswith('.pdf') else 'Text/Generic'
        print(f"New {file_type} File Message FROM: {message.author.name} : {cleaned_text}")
        print(f"Processing {file_type} File")
        response_text = await process_file_attachment(attachment, cleaned_text, settings)
        await split_and_send_messages(message, response_text, 1900)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(FileProcessor(bot))
