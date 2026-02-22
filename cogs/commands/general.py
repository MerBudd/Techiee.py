"""
General commands cog - User-accessible general commands.
"""
import discord
from discord import app_commands
from discord.ext import commands

from config import cooldowns
from utils.config_manager import dynamic_config
from utils.gemini import tracked_threads, message_history, get_history_key, pending_context


class General(commands.Cog):
    """Cog for general user commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='help', description='View all available commands and learn about Techiee\'s features.')
    async def help(self, interaction: discord.Interaction):
        # Display help information using embed (supports up to 4096 chars)
        embed = discord.Embed(
            title="<:techiee:1465670132050300960> Techiee Help",
            description=dynamic_config.help_text[dynamic_config.help_text.find("Hey there!"):],  # Skip the header
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='create-thread', description='Create a dedicated thread where Techiee responds to every message.')
    async def create_thread(self, interaction: discord.Interaction, name: str):
        # Create a tracked thread for bot conversations.
        try:
            thread = await interaction.channel.create_thread(name=name, type=discord.ChannelType.public_thread, auto_archive_duration=60)
            tracked_threads.append(thread.id)
            await interaction.response.send_message(f"Thread '{name}' created! Go to <#{thread.id}> to join the thread and chat with me there.")
        except Exception as e:
            await interaction.response.send_message("❗️ Error creating thread!")
    
    @app_commands.checks.cooldown(1, cooldowns.get("forget", 5))
    @app_commands.command(name='forget', description='Clear your conversation history with Techiee in the current context (DM, thread, or channel).')
    async def forget(self, interaction: discord.Interaction):
        """Clear message history for the current context."""
        # Determine the appropriate history key based on context
        channel_id = interaction.channel.id
        user_id = interaction.user.id
        
        # Thread context
        if channel_id in tracked_threads:
            history_key = ("thread", channel_id)
            scope_msg = "this thread"
        # DM context
        elif isinstance(interaction.channel, discord.DMChannel):
            history_key = ("dm", user_id)
            scope_msg = "your DMs"
        # Tracked channel context
        elif channel_id in dynamic_config.tracked_channels:
            history_key = ("tracked", user_id)
            scope_msg = f"{interaction.user.mention} in this channel"
        else:
            # @mention context - global per-user history
            history_key = ("mention", user_id)
            scope_msg = "your @mentions"
        
        if history_key in message_history:
            del message_history[history_key]
            # Also clear any pending context for this key
            if history_key in pending_context:
                del pending_context[history_key]
            await interaction.response.send_message(f"🧼 History cleared for {scope_msg}!")
        elif history_key in pending_context:
            # Only pending context exists
            del pending_context[history_key]
            await interaction.response.send_message(f"🧼 Pending context cleared for {scope_msg}!")
        else:
            await interaction.response.send_message("📭 No history to clear in this context.")


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(General(bot))
