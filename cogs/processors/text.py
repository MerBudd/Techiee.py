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
)
from config import max_history


class TextProcessor(commands.Cog):
    """Cog for processing text-only messages."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, cleaned_text, settings, reply_chain_context=None):
        """Process a text-only message with history support.
        
        Args:
            message: Discord message object
            cleaned_text: Cleaned message content
            settings: User/context settings
            reply_chain_context: Optional list of Content objects from reply chain
        """
        print(f"New Text Message FROM: {message.author.name} : {cleaned_text}")
        
        # Default to empty list if not provided
        if reply_chain_context is None:
            reply_chain_context = []
        
        # Get user info for system prompt
        user_display_name = message.author.display_name
        user_username = message.author.name
        
        # Check for pending context from /context command
        pending_ctx = get_pending_context(message.author.id)
        if pending_ctx:
            remaining = decrement_pending_context(message.author.id)
            print(f"📚 Using pending context ({len(pending_ctx)} messages) for {message.author.name}, {remaining} uses left")
        
        # Regular text conversation with history
        if max_history == 0:
            # Even with no history, we can still use pending context and reply chain
            user_content = create_user_content([Part(text=cleaned_text)])
            contents = reply_chain_context + pending_ctx + [user_content]
            response_text = await generate_response_with_text(contents, settings, user_display_name, user_username)
            
            async def retry_callback():
                return await generate_response_with_text(contents, settings, user_display_name, user_username)
            
            await send_response_with_retry(message, response_text, retry_callback)
            return
        
        # Create user content with text part
        user_content = create_user_content([Part(text=cleaned_text)])
        
        # Get existing history (context-aware) and add new user message
        # Order: history + reply_chain + pending_context + user_message
        history = get_message_history_contents(message)
        contents = history + reply_chain_context + pending_ctx + [user_content]
        
        # Generate response with full history context
        response_text = await generate_response_with_text(contents, settings, user_display_name, user_username)
        
        # Define retry callback that re-generates with same context
        async def retry_callback():
            return await generate_response_with_text(contents, settings, user_display_name, user_username)
        
        # Define history update callback for when response succeeds
        # Note: We don't add pending_ctx or reply_chain to permanent history, only user's actual message
        async def update_history(response_text):
            update_message_history(message, user_content)
            model_content = create_model_content(response_text)
            update_message_history(message, model_content)
        
        await send_response_with_retry(message, response_text, retry_callback, update_history)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(TextProcessor(bot))

