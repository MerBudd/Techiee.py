"""
YouTube processor cog - Handles YouTube URL processing.
"""
from discord.ext import commands

from utils.helpers import split_and_send_messages
from utils.gemini import (
    process_youtube_url,
    update_message_history,
    get_message_history_contents,
    create_user_content,
    create_model_content,
)
from config import max_history


class YouTubeProcessor(commands.Cog):
    """Cog for processing YouTube URLs."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def process(self, message, url, cleaned_text, settings):
        """Process a YouTube URL with history support."""
        print(f"New YouTube URL FROM: {message.author.name} : {url}")
        print("Processing YouTube Video")
        
        # Get history if enabled (context-aware)
        history = get_message_history_contents(message) if max_history > 0 else None
        
        # Process YouTube URL with history context
        response_text, user_parts = await process_youtube_url(url, cleaned_text, settings, history)
        
        # Update history with this interaction (context-aware)
        if max_history > 0 and user_parts is not None:
            user_content = create_user_content(user_parts)
            update_message_history(message, user_content)
            model_content = create_model_content(response_text)
            update_message_history(message, model_content)
        
        await split_and_send_messages(message, response_text, 1900, message.author.id)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(YouTubeProcessor(bot))
