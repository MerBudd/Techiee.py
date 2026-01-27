"""
Router cog - Routes incoming messages to appropriate processor cogs.
"""
import discord
from discord.ext import commands
import asyncio

from config import tracked_channels
from utils.helpers import clean_discord_message, extract_url, is_youtube_url
from utils.gemini import tracked_threads, get_settings


class Router(commands.Cog):
    """Cog for routing messages to the appropriate processor."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for messages and spawn processing task."""
        asyncio.create_task(self.route_message(message))
    
    async def route_message(self, message):
        """Route incoming messages to the appropriate processor cog."""
        # Ignore messages sent by the bot or if mention everyone is used
        if message.author == self.bot.user or message.mention_everyone:
            return
        
        # Ignore other bots
        if message.author.bot:
            return
        
        # Check if bot was mentioned in the message
        bot_mentioned = self.bot.user in message.mentions

        # Check if the message is a DM, in tracked channels/threads, or mentions the bot
        if isinstance(message.channel, discord.DMChannel) or message.channel.id in tracked_channels or message.channel.id in tracked_threads or bot_mentioned:
            cleaned_text = clean_discord_message(message.content)
            
            # Get settings for this context
            settings = get_settings(message)
            
            # Use Discord's built-in typing context manager
            async with message.channel.typing():
                # Check for attachments
                if message.attachments:
                    attachment = message.attachments[0]  # Process first attachment
                    print(f"New Attachment Message FROM: {message.author.name} : {cleaned_text}")
                    
                    # Image processing
                    if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                        image_processor = self.bot.get_cog('ImageProcessor')
                        if image_processor:
                            await image_processor.process(message, attachment, cleaned_text, settings)
                        return
                    
                    # Video processing
                    elif any(attachment.filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.mpeg', '.mpg', '.wmv', '.flv', '.3gp']):
                        video_processor = self.bot.get_cog('VideoProcessor')
                        if video_processor:
                            await video_processor.process(message, attachment, cleaned_text, settings)
                        return
                    
                    # PDF and text file processing
                    else:
                        file_processor = self.bot.get_cog('FileProcessor')
                        if file_processor:
                            await file_processor.process(message, attachment, cleaned_text, settings)
                        return
                
                # Text-only message processing
                else:
                    # Check for URLs
                    url = extract_url(cleaned_text)
                    if url is not None:
                        print(f"Got URL: {url}")
                        if is_youtube_url(url):
                            youtube_processor = self.bot.get_cog('YouTubeProcessor')
                            if youtube_processor:
                                await youtube_processor.process(message, url, cleaned_text, settings)
                        else:
                            website_processor = self.bot.get_cog('WebsiteProcessor')
                            if website_processor:
                                await website_processor.process(message, url, cleaned_text, settings)
                        return
                    
                    # Regular text conversation
                    text_processor = self.bot.get_cog('TextProcessor')
                    if text_processor:
                        await text_processor.process(message, cleaned_text, settings)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Router(bot))
