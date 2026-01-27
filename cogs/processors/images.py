"""
Image processor cog - Handles image attachment processing.
"""
from discord.ext import commands

from utils.helpers import split_and_send_messages
from utils.gemini import (
    process_image_attachment,
    update_message_history,
    get_message_history_contents,
    create_user_content,
    create_model_content,
)
from config import max_history


class ImageProcessor(commands.Cog):
    """Cog for processing image attachments."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, attachment, cleaned_text, settings):
        """Process an image attachment with history support."""
        print(f"New Image Message FROM: {message.author.name} : {cleaned_text}")
        print("Processing Image")
        
        # Get history if enabled
        history = get_message_history_contents(message.author.id) if max_history > 0 else None
        
        # Process image with history context
        response_text, history_parts, uploaded_file = await process_image_attachment(
            attachment, cleaned_text, settings, history
        )
        
        # Update history with this interaction (using sanitized text-only parts)
        if max_history > 0 and history_parts is not None:
            user_content = create_user_content(history_parts)
            update_message_history(message.author.id, user_content)
            model_content = create_model_content(response_text)
            update_message_history(message.author.id, model_content)
        
        await split_and_send_messages(message, response_text, 1900)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(ImageProcessor(bot))
