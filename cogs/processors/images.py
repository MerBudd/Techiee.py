"""
Image processor cog - Handles image attachment processing.
"""
from discord.ext import commands

from utils.retry import send_response_with_retry
from utils.gemini import (
    process_image_attachments,
    update_message_history,
    get_message_history_contents,
    create_user_content,
    create_model_content,
    get_pending_context,
    decrement_pending_context,
    get_history_key,
)
from config import max_history


class ImageProcessor(commands.Cog):
    """Cog for processing image attachments."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, attachments, cleaned_text, settings, reply_chain_context=None):
        """Process image attachment(s) with history support.
        
        Args:
            message: Discord message object
            attachments: List of image attachments (supports multiple)
            cleaned_text: Cleaned message content
            settings: User/context settings
            reply_chain_context: Optional list of Content objects from reply chain
        """
        # Handle single attachment for backwards compatibility
        if not isinstance(attachments, list):
            attachments = [attachments]
        
        if reply_chain_context is None:
            reply_chain_context = []
        
        print(f"New Image Message FROM: {message.author.name} : {cleaned_text}")
        print(f"Processing {len(attachments)} Image(s)")
        
        # Get user info for system prompt
        user_display_name = message.author.display_name
        user_username = message.author.name
        
        # Check for pending context from /context command (scoped by history key)
        history_key = get_history_key(message)
        pending_ctx = get_pending_context(history_key)
        if pending_ctx:
            from utils.gemini import get_pending_context_remaining
            remaining_before = get_pending_context_remaining(history_key)
            print(f"📚 Using pending context ({len(pending_ctx)} messages) for {message.author.name}, {remaining_before - 1} uses left after this")
            decrement_pending_context(history_key)
        
        # Get history if enabled (context-aware) and combine with reply chain and pending context
        if max_history > 0:
            history = get_message_history_contents(message) + reply_chain_context + pending_ctx
        else:
            history = (reply_chain_context + pending_ctx) if (reply_chain_context or pending_ctx) else None
        
        # Process image(s) with history context
        response_text, history_parts, uploaded_files = await process_image_attachments(
            attachments, cleaned_text, settings, history, user_display_name, user_username
        )
        
        # Define retry callback
        async def retry_callback():
            result, _, _ = await process_image_attachments(
                attachments, cleaned_text, settings, history, user_display_name, user_username
            )
            return result
        
        # Define history update callback
        async def update_history(response_text):
            if max_history > 0 and history_parts is not None:
                user_content = create_user_content(history_parts)
                update_message_history(message, user_content)
                model_content = create_model_content(response_text)
                update_message_history(message, model_content)
        
        await send_response_with_retry(message, response_text, retry_callback, update_history, history_key)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(ImageProcessor(bot))

