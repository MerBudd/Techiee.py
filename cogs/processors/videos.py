"""
Video processor cog - Handles video attachment processing.
"""
from discord.ext import commands

from utils.retry import send_response_with_retry
from utils.gemini import (
    process_video_attachment,
    update_message_history,
    get_message_history_contents,
    create_user_content,
    create_model_content,
    get_and_clear_pending_context,
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
        
        # Get user info for system prompt
        user_display_name = message.author.display_name
        user_username = message.author.name
        
        # Check for pending context from /context command
        pending_ctx = get_and_clear_pending_context(message.author.id)
        if pending_ctx:
            print(f"📚 Using pending context ({len(pending_ctx)} messages) for {message.author.name}")
        
        # Get history if enabled (context-aware) and combine with pending context
        if max_history > 0:
            history = get_message_history_contents(message) + pending_ctx
        else:
            history = pending_ctx if pending_ctx else None
        
        # Process video with history context
        response_text, history_parts, uploaded_file = await process_video_attachment(
            attachment, cleaned_text, settings, history, user_display_name, user_username
        )
        
        # Define retry callback
        async def retry_callback():
            result, _, _ = await process_video_attachment(
                attachment, cleaned_text, settings, history, user_display_name, user_username
            )
            return result
        
        # Define history update callback
        async def update_history(response_text):
            if max_history > 0 and history_parts is not None:
                user_content = create_user_content(history_parts)
                update_message_history(message, user_content)
                model_content = create_model_content(response_text)
                update_message_history(message, model_content)
        
        await send_response_with_retry(message, response_text, retry_callback, update_history)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(VideoProcessor(bot))
