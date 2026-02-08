"""
General commands cog - User-accessible general commands.
"""
import discord
from discord import app_commands
from discord.ext import commands

from config import help_text, tracked_channels
from utils.gemini import tracked_threads, message_history, get_history_key


class General(commands.Cog):
    """Cog for general user commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='help', description='Shows help(ful) info and commands for Techiee.')
    async def help(self, interaction: discord.Interaction):
        # Display help information using embed (supports up to 4096 chars)
        embed = discord.Embed(
            title="<:techiee:1465670132050300960> Techiee Help",
            description=help_text[help_text.find("Hey there!"):],  # Skip the header
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name='createthread', description='Create a thread in which Techiee will respond to every message.')
    async def create_thread(self, interaction: discord.Interaction, name: str):
        # Create a tracked thread for bot conversations.
        try:
            thread = await interaction.channel.create_thread(name=name, type=discord.ChannelType.public_thread, auto_archive_duration=60)
            tracked_threads.append(thread.id)
            await interaction.response.send_message(f"Thread '{name}' created! Go to <#{thread.id}> to join the thread and chat with me there.")
        except Exception as e:
            await interaction.response.send_message("❗️ Error creating thread!")
    
    @app_commands.command(name='forget', description='Clear your message history with Techiee.')
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
        elif channel_id in tracked_channels:
            history_key = ("tracked", user_id)
            scope_msg = f"{interaction.user.mention} in this channel"
        else:
            # @mention context - global per-user history
            history_key = ("mention", user_id)
            scope_msg = "your @mentions"
        
        if history_key in message_history:
            del message_history[history_key]
            await interaction.response.send_message(f"🧼 History cleared for {scope_msg}!")
        else:
            await interaction.response.send_message("📭 No history to clear in this context.")


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(General(bot))
