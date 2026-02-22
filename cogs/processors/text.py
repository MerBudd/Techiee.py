"""
Text processor cog - Handles text-only chat messages.
"""
from discord.ext import commands

from google.genai.types import Part

from utils.retry import send_response_with_retry
from utils.gemini import (
    generate_response_with_text,
    update_message_history,
    get_message_history_contents,
    create_user_content,
    create_model_content,
    get_pending_context,
    decrement_pending_context,
    get_history_key,
)

from config import max_history


class TextProcessor(commands.Cog):
    """Cog for processing text-only messages."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, cleaned_text, settings, reply_chain_context=None, media_parts=None):
        """Process a text-only message with history support.
        
        Args:
            message: Discord message object
            cleaned_text: Cleaned message content
            settings: User/context settings
            reply_chain_context: Optional list of Content objects from reply chain
            media_parts: Optional list of Part objects (sticker/GIF/emoji images)
        """
        from utils.helpers import log_new_message
        log_new_message("Text", message, cleaned_text)
        
        # Default to empty list if not provided
        if reply_chain_context is None:
            reply_chain_context = []
        if media_parts is None:
            media_parts = []
        
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

        
        # Build user content parts: text + any media (sticker/GIF/emoji images)
        user_parts = [Part(text=cleaned_text)] + media_parts
        
        # Regular text conversation with history
        if max_history == 0:
            # Even with no history, we can still use pending context and reply chain
            user_content = create_user_content(user_parts)
            contents = reply_chain_context + pending_ctx + [user_content]
            response_text = await generate_response_with_text(contents, settings, user_display_name, user_username)
            
            async def retry_callback():
                return await generate_response_with_text(contents, settings, user_display_name, user_username)
            
            await send_response_with_retry(message, response_text, retry_callback, history_key=history_key)
            return
        
        # Create user content with text + media parts
        user_content = create_user_content(user_parts)
        
        # Get existing history (context-aware) and add new user message
        # Order: history + reply_chain + pending_context + user_message
        history = get_message_history_contents(message)
        contents = history + reply_chain_context + pending_ctx + [user_content]
        
        # Generate response with full history context
        response_text = await generate_response_with_text(contents, settings, user_display_name, user_username)
        
        # Define retry callback that re-generates with same context
        async def retry_callback():
            return await generate_response_with_text(contents, settings, user_display_name, user_username)
        
        # Store full user_parts so images/stickers/GIFs stay in history
        async def update_history(response_text):
            user_msg_content = create_user_content(user_parts)
            update_message_history(message, user_msg_content)
            model_content = create_model_content(response_text)
            update_message_history(message, model_content)
        
        await send_response_with_retry(message, response_text, retry_callback, update_history, history_key)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(TextProcessor(bot))

