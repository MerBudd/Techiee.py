"""
Router cog - Routes incoming messages to appropriate processor cogs.
"""
import discord
from discord.ext import commands
import asyncio

from config import tracked_channels
from utils.helpers import clean_discord_message, extract_url, is_youtube_url
from utils.gemini import tracked_threads, get_settings, has_auto_respond_for_channel
from utils.typing import typing_manager

from utils.reply_chain import fetch_reply_chain


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
        
        # Check if user has pending context for this channel (auto-respond without @mention)
        has_context_for_channel = has_auto_respond_for_channel(message.author.id, message.channel.id)

        # Check if the message is a DM, in tracked channels/threads, mentions the bot, or has pending context for this channel
        if isinstance(message.channel, discord.DMChannel) or message.channel.id in tracked_channels or message.channel.id in tracked_threads or bot_mentioned or has_context_for_channel:
            cleaned_text = clean_discord_message(message.content)
            
            # Get settings for this context
            settings = get_settings(message)
            
            # Fetch reply chain context if this is a reply
            reply_chain_context = []
            if message.reference:
                try:
                    reply_chain_context = await fetch_reply_chain(message, max_depth=10)
                    if reply_chain_context:
                        print(f"📎 Fetched reply chain with {len(reply_chain_context)} messages")
                except Exception as e:
                    print(f"⚠️ Failed to fetch reply chain: {e}")
            
            # Start typing indicator with reference counting (handles concurrent messages)
            await typing_manager.start_typing(message.channel)
            try:
                # Enrich cleaned text with sticker and GIF context
                enriched_text = cleaned_text
                
                # Add sticker info to context
                if message.stickers:
                    sticker_info = ", ".join([f"[Sticker: {s.name}]" for s in message.stickers])
                    enriched_text = f"{enriched_text}\n{sticker_info}" if enriched_text else sticker_info
                
                # Add GIF and embed info to context
                if message.embeds:
                    for embed in message.embeds:
                        if embed.type == "gifv" or (embed.provider and embed.provider.name and embed.provider.name.lower() in ("tenor", "giphy")):
                            gif_url = embed.url or (embed.thumbnail.url if embed.thumbnail else None)
                            if gif_url:
                                gif_text = f"[GIF: {gif_url}]"
                                enriched_text = f"{enriched_text}\n{gif_text}" if enriched_text else gif_text
                        elif embed.title or embed.description:
                            # Rich embeds: extract key info
                            embed_parts = []
                            if embed.title:
                                embed_parts.append(f"Title: {embed.title}")
                            if embed.description:
                                embed_parts.append(f"Description: {embed.description}")
                            if embed.fields:
                                for field in embed.fields:
                                    embed_parts.append(f"{field.name}: {field.value}")
                            if embed_parts:
                                embed_text = "[Embed] " + " | ".join(embed_parts) + " [/Embed]"
                                enriched_text = f"{enriched_text}\n{embed_text}" if enriched_text else embed_text
                
                # Check for attachments
                if message.attachments:
                    # Collect all attachments by type
                    images = []
                    videos = []
                    files = []
                    
                    for attachment in message.attachments:
                        filename_lower = attachment.filename.lower()
                        if any(filename_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                            images.append(attachment)
                        elif any(filename_lower.endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.mpeg', '.mpg', '.wmv', '.flv', '.3gp']):
                            videos.append(attachment)
                        else:
                            files.append(attachment)
                    
                    print(f"New Attachment Message FROM: {message.author.name} : {enriched_text}")
                    print(f"  Images: {len(images)}, Videos: {len(videos)}, Files: {len(files)}")
                    
                    # Process by type priority: images > videos > files
                    # If mixed, process all together via the appropriate processor
                    if images:
                        image_processor = self.bot.get_cog('ImageProcessor')
                        if image_processor:
                            await image_processor.process(message, images, enriched_text, settings, reply_chain_context)
                        return
                    
                    if videos:
                        video_processor = self.bot.get_cog('VideoProcessor')
                        if video_processor:
                            await video_processor.process(message, videos, enriched_text, settings, reply_chain_context)
                        return
                    
                    if files:
                        file_processor = self.bot.get_cog('FileProcessor')
                        if file_processor:
                            await file_processor.process(message, files, enriched_text, settings, reply_chain_context)
                        return
                
                # Text-only message processing (may include sticker/GIF/embed enrichment)
                else:
                    # Check for URLs
                    url = extract_url(enriched_text)
                    if url is not None:
                        print(f"Got URL: {url}")
                        if is_youtube_url(url):
                            youtube_processor = self.bot.get_cog('YouTubeProcessor')
                            if youtube_processor:
                                await youtube_processor.process(message, url, enriched_text, settings, reply_chain_context)
                        else:
                            website_processor = self.bot.get_cog('WebsiteProcessor')
                            if website_processor:
                                await website_processor.process(message, url, enriched_text, settings, reply_chain_context)
                        return
                    
                    # Regular text conversation (includes stickers, GIFs, embeds in enriched_text)
                    text_processor = self.bot.get_cog('TextProcessor')
                    if text_processor:
                        await text_processor.process(message, enriched_text, settings, reply_chain_context)
            finally:
                # Always stop typing when done (ref-counted, so only stops when all done)
                await typing_manager.stop_typing(message.channel)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Router(bot))

