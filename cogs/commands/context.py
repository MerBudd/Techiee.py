"""
Context command cog - Loads channel messages as temporary context.
"""
import discord
from discord import app_commands
from discord.ext import commands

from google.genai.types import Part, Content

from config import tracked_channels, cooldowns
from utils.gemini import set_pending_context, tracked_threads


class Context(commands.Cog):
    """Cog for the /context command."""
    
    def __init__(self, bot):
        self.bot = bot
    
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
        is_tracked = channel_id in tracked_channels or channel_id in tracked_threads
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
            
            # Convert to Content objects
            context_contents = []
            for msg in messages:
                # Format: "[YYYY-MM-DD HH:MM] DisplayName (@username): message content"
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
                text = f"[{timestamp}] {msg.author.display_name} (@{msg.author.name}): {msg.content}"
                
                # Handle attachments
                if msg.attachments:
                    attachment_names = [att.filename for att in msg.attachments]
                    text += f" [Attachments: {', '.join(attachment_names)}]"
                
                # Handle embeds
                if msg.embeds:
                    embed_count = len(msg.embeds)
                    text += f" [Embeds: {embed_count}]"
                
                # Create as user content (treated as context from others)
                context_contents.append(Content(role="user", parts=[Part(text=text)]))
            
            # Store in pending context
            # Build context_key based on where we are (same logic as history keys)
            if channel_id in tracked_threads:
                context_key = ("thread", channel_id)
            elif is_dm:
                context_key = ("dm", user_id)
            elif channel_id in tracked_channels:
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
            elif channel_id in tracked_channels:
                scope_msg = f"{interaction.user.mention} in this tracked channel"
            else:
                scope_msg = f"{interaction.user.mention} via @mentions"

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
