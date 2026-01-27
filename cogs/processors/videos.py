"""
Video processor cog - Handles video attachment processing.
"""
from discord.ext import commands

from utils.helpers import split_and_send_messages
from utils.gemini import (
    process_video_attachment,
    update_message_history,
    get_message_history_contents,
    create_user_content,
    create_model_content,
)
from config import max_history


class VideoProcessor(commands.Cog):
    """Cog for processing video attachments."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, attachment, cleaned_text, settings):
        """Process a video attachment with history support."""
        print(f"New Video Message FROM: {message.author.name} : {cleaned_text}")
        print("Processing Video")
        
        # Get history if enabled
        history = get_message_history_contents(message.author.id) if max_history > 0 else None
        
        # Process video with history context
        response_text, user_parts, uploaded_file = await process_video_attachment(
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
    await bot.add_cog(VideoProcessor(bot))
