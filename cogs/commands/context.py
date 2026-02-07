"""
Context command cog - Loads channel messages as temporary context.
"""
import discord
from discord import app_commands
from discord.ext import commands

from google.genai.types import Part, Content

from utils.gemini import set_pending_context


class Context(commands.Cog):
    """Cog for the /context command."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='context', description='Load recent channel messages as context for your next message.')
    @app_commands.describe(count='Number of messages to load (1-50, default 10)')
    async def context(self, interaction: discord.Interaction, count: int = 10):
        """Load recent channel messages as temporary context for the next prompt."""
        
        # Validate count
        if count < 1:
            count = 1
        elif count > 50:
            count = 50
        
        # Defer with ephemeral response
        await interaction.response.defer(ephemeral=True)
        
        user_id = interaction.user.id
        bot_id = self.bot.user.id
        
        try:
            # Fetch messages from channel history
            # We fetch more than needed to account for filtering
            messages = []
            async for msg in interaction.channel.history(limit=count * 3):
                # Skip the command invocation itself (if present)
                if msg.interaction and msg.interaction.id == interaction.id:
                    continue
                    
                # Skip user's own messages
                if msg.author.id == user_id:
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
                await interaction.followup.send(
                    "❌ No messages found to load as context (your messages and my replies to you are excluded).",
                    ephemeral=True
                )
                return
            
            # Reverse to get chronological order (oldest first)
            messages.reverse()
            
            # Convert to Content objects
            context_contents = []
            for msg in messages:
                # Format: "Username: message content"
                text = f"{msg.author.display_name}: {msg.content}"
                
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
            set_pending_context(user_id, context_contents)
            
            await interaction.followup.send(
                f"✅ **Context loaded!** {len(messages)} message(s) from this channel are now cached.\n\n"
                f"📝 **Send your prompt now** - the context will be used for your next message only.",
                ephemeral=True
            )
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to read message history in this channel.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error loading context: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Context(bot))
