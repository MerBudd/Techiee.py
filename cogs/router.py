"""
Router cog - Routes incoming messages to appropriate processor cogs.
"""
import discord
from discord.ext import commands
import asyncio
import aiohttp

from google.genai.types import Part

from config import tracked_channels
from utils.helpers import clean_discord_message, extract_url, is_youtube_url, extract_custom_emojis, get_emoji_cdn_url
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
            import time as _time
            _process_start = _time.monotonic()
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
                # Enrich cleaned text with sticker, GIF, and emoji context
                # Also collect media_parts (actual images) for visual content
                enriched_text = cleaned_text
                media_parts = []  # List of Part objects with inline_data
                
                async with aiohttp.ClientSession() as session:
                    # Download sticker images
                    if message.stickers:
                        for sticker in message.stickers:
                            label = f"[Sticker: {sticker.name}]"
                            enriched_text = f"{enriched_text}\n{label}" if enriched_text else label
                            if hasattr(sticker, 'url') and sticker.url:
                                try:
                                    async with session.get(str(sticker.url)) as resp:
                                        if resp.status == 200:
                                            image_bytes = await resp.read()
                                            content_type = resp.headers.get('Content-Type', 'image/png')
                                            if 'json' not in content_type and 'lottie' not in content_type:
                                                media_parts.append(Part(text=label))
                                                media_parts.append(Part(inline_data={
                                                    "mime_type": content_type.split(';')[0],
                                                    "data": image_bytes
                                                }))
                                except Exception as e:
                                    print(f"⚠️ Failed to download sticker {sticker.name}: {e}")
                    
                    # Download GIF thumbnails and include embed info
                    if message.embeds:
                        for embed in message.embeds:
                            if embed.type == "gifv" or (embed.provider and embed.provider.name and embed.provider.name.lower() in ("tenor", "giphy")):
                                gif_url = None
                                if embed.thumbnail and embed.thumbnail.url:
                                    gif_url = embed.thumbnail.url
                                elif embed.url:
                                    gif_url = embed.url
                                if gif_url:
                                    provider_name = embed.provider.name if embed.provider and embed.provider.name else "unknown"
                                    label = f"[GIF from {provider_name}]"
                                    enriched_text = f"{enriched_text}\n{label}" if enriched_text else label
                                    try:
                                        async with session.get(str(gif_url)) as resp:
                                            if resp.status == 200:
                                                image_bytes = await resp.read()
                                                content_type = resp.headers.get('Content-Type', 'image/gif')
                                                if content_type.startswith('image/') or content_type.startswith('video/'):
                                                    media_parts.append(Part(text=label))
                                                    media_parts.append(Part(inline_data={
                                                        "mime_type": content_type.split(';')[0],
                                                        "data": image_bytes
                                                    }))
                                    except Exception as e:
                                        print(f"⚠️ Failed to download GIF: {e}")
                            elif embed.title or embed.description:
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
                    
                    # Download custom emoji images
                    custom_emojis = extract_custom_emojis(message.content)
                    if custom_emojis:
                        for name, emoji_id, animated in custom_emojis:
                            emoji_url = get_emoji_cdn_url(emoji_id, animated)
                            label = f"[Custom Emoji: {name}]"
                            try:
                                async with session.get(emoji_url) as resp:
                                    if resp.status == 200:
                                        image_bytes = await resp.read()
                                        content_type = resp.headers.get('Content-Type', 'image/png')
                                        media_parts.append(Part(text=label))
                                        media_parts.append(Part(inline_data={
                                            "mime_type": content_type.split(';')[0],
                                            "data": image_bytes
                                        }))
                            except Exception as e:
                                print(f"⚠️ Failed to download emoji {name}: {e}")
                
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
                
                # Text-only message processing (may include sticker/GIF/embed/emoji media)
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
                    
                    # Regular text conversation (includes stickers, GIFs, embeds, emojis as visual media)
                    text_processor = self.bot.get_cog('TextProcessor')
                    if text_processor:
                        await text_processor.process(message, enriched_text, settings, reply_chain_context, media_parts)
            finally:
                # Safety net: force-stop typing if still active
                # (Normally, retry.py already stops typing right before sending messages)
                await typing_manager.force_stop_immediate(message.channel)
                _total_elapsed = _time.monotonic() - _process_start
                print(f"⏱️ Total processing time for {message.author.name}: {_total_elapsed:.2f}s")


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Router(bot))

