"""
Text processor cog - Handles text-only chat messages.
"""
from discord.ext import commands

from google.genai.types import Part

from utils.helpers import split_and_send_messages
from utils.gemini import (
    generate_response_with_text,
    update_message_history,
    get_message_history_contents,
    create_user_content,
    create_model_content,
)
from config import max_history


class TextProcessor(commands.Cog):
    """Cog for processing text-only messages."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, cleaned_text, settings):
        """Process a text-only message with history support."""
        print(f"New Text Message FROM: {message.author.name} : {cleaned_text}")
        
        # Regular text conversation with history
        if max_history == 0:
            response_text = await generate_response_with_text(cleaned_text, settings)
            await split_and_send_messages(message, response_text, 1900)
            return
        
        # Create user content with text part
        user_content = create_user_content([Part.from_text(cleaned_text)])
        
        # Get existing history and add new user message
        history = get_message_history_contents(message.author.id)
        contents = history + [user_content]
        
        # Generate response with full history context
        response_text = await generate_response_with_text(contents, settings)
        
        # Add user message and AI response to history
        update_message_history(message.author.id, user_content)
        model_content = create_model_content(response_text)
        update_message_history(message.author.id, model_content)
        
        await split_and_send_messages(message, response_text, 1900)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(TextProcessor(bot))
