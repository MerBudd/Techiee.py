"""
File processor cog - Handles PDF and text file attachment processing.
"""
from discord.ext import commands

from utils.helpers import split_and_send_messages
from utils.gemini import (
    process_file_attachment,
    update_message_history,
    get_message_history_contents,
    create_user_content,
    create_model_content,
)
from config import max_history


class FileProcessor(commands.Cog):
    """Cog for processing PDF and text file attachments."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, attachment, cleaned_text, settings):
        """Process a PDF or text file attachment with history support."""
        file_type = 'PDF' if attachment.filename.lower().endswith('.pdf') else 'Text/Generic'
        print(f"New {file_type} File Message FROM: {message.author.name} : {cleaned_text}")
        print(f"Processing {file_type} File")
        
        # Get history if enabled
        history = get_message_history_contents(message.author.id) if max_history > 0 else None
        
        # Process file with history context
        response_text, user_parts, uploaded_file = await process_file_attachment(
            attachment, cleaned_text, settings, history
        )
        
        # Update history with this interaction
        if max_history > 0 and user_parts is not None:
            user_content = create_user_content(user_parts)
            update_message_history(message.author.id, user_content)
            model_content = create_model_content(response_text)
            update_message_history(message.author.id, model_content)
        
        await split_and_send_messages(message, response_text, 1900)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(FileProcessor(bot))
