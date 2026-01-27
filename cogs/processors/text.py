"""
Text processor cog - Handles text-only chat messages.
"""
from discord.ext import commands

from utils.helpers import split_and_send_messages
from utils.gemini import (
    generate_response_with_text,
    update_message_history,
    get_formatted_message_history,
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
        
        # Add user's question to history
        update_message_history(message.author.id, cleaned_text)
        response_text = await generate_response_with_text(get_formatted_message_history(message.author.id), settings)
        # Add AI response to history
        update_message_history(message.author.id, response_text)
        await split_and_send_messages(message, response_text, 1900)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(TextProcessor(bot))
