"""
Context command cog - Loads channel messages as temporary context.
"""
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from google.genai.types import Part, Content

from utils.config_manager import dynamic_config
from utils.gemini import set_pending_context, tracked_threads


class Context(commands.Cog):
    """Cog for the /context command."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.checks.cooldown(1, dynamic_config.cooldowns.get("context", 7))
    @app_commands.command(name='context', description='Load recent channel messages as context so Techiee can reference them.')
    @app_commands.describe(
        count='Number of messages to load (1-50, default 10)',
        lasts_for='Number of your messages this context lasts for (1-20, default 5)',
        include_user='Only include messages from this user (optional)',
        exclude_user='Exclude messages from this user (optional)'
    )
    async def context(self, interaction: discord.Interaction, count: int = 10, lasts_for: int = 5, include_user: discord.User = None, exclude_user: discord.User = None):
        """Load recent channel messages as temporary context for the next prompts."""
        
        # Validate count
        if count < 1:
            count = 1
        elif count > 50:
            count = 50
        
        # Validate lasts_for
        if lasts_for < 1:
            lasts_for = 1
        elif lasts_for > 20:
            lasts_for = 20
        
        # Defer with public response (so everyone sees context is loaded)
        await interaction.response.defer(ephemeral=False)
        
        user_id = interaction.user.id
        bot_id = self.bot.user.id
        channel_id = interaction.channel.id
        
        # Determine if this is a tracked context (tracked channel or thread)
        is_tracked = channel_id in dynamic_config.tracked_channels or channel_id in tracked_threads
        is_dm = isinstance(interaction.channel, discord.DMChannel)
        
        try:
            # Fetch messages from channel history
            # We fetch more than needed to account for filtering
            messages = []
            async for msg in interaction.channel.history(limit=count * 3):
                # Skip the command invocation itself (if present)
                if msg.interaction_metadata and msg.interaction_metadata.id == interaction.id:
                    continue
                
                # Apply include_user filter if specified
                if include_user and msg.author.id != include_user.id:
                    continue
                
                # Apply exclude_user filter if specified
                if exclude_user and msg.author.id == exclude_user.id:
                    continue
                
                # In tracked channels/threads: skip user's own messages
                # In non-tracked channels: include user's own messages
                if is_tracked and msg.author.id == user_id:
                    continue
                
                # Skip bot's messages that are replies to the user
                if msg.author.id == bot_id:
                    # Check if this is a reply to the user
                    if msg.reference and msg.reference.resolved:
                        if hasattr(msg.reference.resolved, 'author') and msg.reference.resolved.author.id == user_id:
                            continue
                    # Also skip if it mentions the user (likely a response)
                    if interaction.user in msg.mentions:
                        continue
                
                # Add to our list
                messages.append(msg)
                
                if len(messages) >= count:
                    break
            
            if not messages:
                filter_note = " (your messages and my replies to you are excluded)" if is_tracked else " (my replies to you are excluded)"
                await interaction.followup.send(
                    f"❌ No messages found to load as context{filter_note}.",
                    ephemeral=False
                )
                return
            
            # Reverse to get chronological order (oldest first)
            messages.reverse()
            
            # Convert to Content objects (with full attachment/embed support)
            context_contents = []
            for msg in messages:
                # Format with clear context labeling (Issue #5)
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
                text = f"[CONTEXT MESSAGE from {msg.author.display_name} (@{msg.author.name}) at {timestamp}]:\n{msg.content}"
                
                parts = [Part(text=text)]
                
                # Download and include image attachments (like reply chain does)
                if msg.attachments:
                    async with aiohttp.ClientSession() as session:
                        for attachment in msg.attachments:
                            if attachment.content_type and attachment.content_type.startswith('image/'):
                                try:
                                    async with session.get(attachment.url) as resp:
                                        if resp.status == 200:
                                            image_bytes = await resp.read()
                                            parts.append(Part(inline_data={
                                                "mime_type": attachment.content_type,
                                                "data": image_bytes
                                            }))
                                except Exception:
                                    parts.append(Part(text=f"[Failed to load image: {attachment.filename}]"))
                            else:
                                parts.append(Part(text=f"[Attachment: {attachment.filename}]"))
                
                # Download sticker images
                if msg.stickers:
                    async with aiohttp.ClientSession() as session:
                        for sticker in msg.stickers:
                            sticker_text = f"[Sticker: {sticker.name}]"
                            if hasattr(sticker, 'url') and sticker.url:
                                try:
                                    async with session.get(str(sticker.url)) as resp:
                                        if resp.status == 200:
                                            image_bytes = await resp.read()
                                            content_type = resp.headers.get('Content-Type', 'image/png')
                                            if 'json' not in content_type and 'lottie' not in content_type:
                                                parts.append(Part(text=sticker_text))
                                                parts.append(Part(inline_data={
                                                    "mime_type": content_type.split(';')[0],
                                                    "data": image_bytes
                                                }))
                                                continue
                                except Exception:
                                    pass
                                sticker_text += f" (URL: {sticker.url})"
                            parts.append(Part(text=sticker_text))
                
                # Download GIF thumbnails and include embed content
                if msg.embeds:
                    async with aiohttp.ClientSession() as session:
                        for embed in msg.embeds:
                            if embed.type == "gifv" or (embed.provider and embed.provider.name and embed.provider.name.lower() in ("tenor", "giphy")):
                                gif_url = None
                                if embed.thumbnail:
                                    gif_url = getattr(embed.thumbnail, 'proxy_url', None) or getattr(embed.thumbnail, 'url', None)
                                if not gif_url and embed.url:
                                    gif_url = embed.url
                                if gif_url:
                                    provider = embed.provider.name if embed.provider and embed.provider.name else "unknown"
                                    try:
                                        async with session.get(str(gif_url)) as resp:
                                            if resp.status == 200:
                                                image_bytes = await resp.read()
                                                content_type = resp.headers.get('Content-Type', 'image/gif')
                                                if content_type.startswith('image/') or content_type.startswith('video/'):
                                                    import tempfile, os
                                                    from utils.gemini import api_key_manager, execute_with_retry
                                                    ext = '.gif' if content_type.startswith('image/gif') else '.mp4'
                                                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                                                        tmp_file.write(image_bytes)
                                                        tmp_path = tmp_file.name
                                                    
                                                    try:
                                                        uploaded_file = await execute_with_retry(
                                                            lambda path=tmp_path: api_key_manager.client.files.upload(file=path)
                                                        )
                                                        parts.append(Part(text=f"[GIF from {provider}]"))
                                                        parts.append(Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type))
                                                    finally:
                                                        try:
                                                            os.unlink(tmp_path)
                                                        except Exception:
                                                            pass
                                                    continue
                                    except Exception:
                                        pass
                                    parts.append(Part(text=f"[GIF: {gif_url}]"))
                            else:
                                embed_lines = []
                                if embed.title:
                                    embed_lines.append(f"Title: {embed.title}")
                                if embed.author and embed.author.name:
                                    embed_lines.append(f"Author: {embed.author.name}")
                                if embed.description:
                                    embed_lines.append(f"Description: {embed.description}")
                                if embed.fields:
                                    for field in embed.fields:
                                        embed_lines.append(f"{field.name}: {field.value}")
                                if embed.footer and embed.footer.text:
                                    embed_lines.append(f"Footer: {embed.footer.text}")
                                if embed.url:
                                    embed_lines.append(f"URL: {embed.url}")
                                if embed_lines:
                                    parts.append(Part(text=f"[Embed]\n" + "\n".join(embed_lines) + "\n[/Embed]"))
                
                # Create as user content (treated as context from others)
                context_contents.append(Content(role="user", parts=parts))
            
            # Store in pending context
            # Build context_key based on where we are (same logic as history keys)
            if channel_id in tracked_threads:
                context_key = ("thread", channel_id)
            elif is_dm:
                context_key = ("dm", user_id)
            elif channel_id in dynamic_config.tracked_channels:
                context_key = ("tracked", user_id)
            else:
                context_key = ("mention", user_id)
            
            # For non-tracked channels (not DM, not tracked), set listen_channel_id for auto-response
            listen_channel = None if (is_tracked or is_dm) else channel_id
            set_pending_context(context_key, context_contents, remaining_uses=lasts_for, listen_channel_id=listen_channel)

            
            # Build response message
            auto_respond_note = ""
            if listen_channel:
                auto_respond_note = "\n🎯 **I'll respond to your next messages here without needing @mention!**"
            
            include_note = ""
            if not is_tracked:
                include_note = " (including your own)"
            
            # Determine scope message for response
            if channel_id in tracked_threads:
                scope_msg = "this thread"
            elif is_dm:
                scope_msg = "your DMs"
            elif channel_id in dynamic_config.tracked_channels:
                scope_msg = f"{interaction.user.mention} in this tracked channel"
            else:
                scope_msg = f"{interaction.user.mention} for @mentions"

            await interaction.followup.send(
                f"✅ **Context loaded for {interaction.user.mention}!** {len(messages)} message(s){include_note} from this channel are now cached for **{scope_msg}**.\n\n"
                f"📝 **Send your prompts** - the context will be used for your next **{lasts_for}** message(s).{auto_respond_note}",
                ephemeral=False
            )
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to read message history in this channel.",
                ephemeral=False
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error loading context: {str(e)}",
                ephemeral=False
            )


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Context(bot))
