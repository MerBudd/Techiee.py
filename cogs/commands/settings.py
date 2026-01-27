"""
Settings commands cog - AI settings commands.
"""
import discord
from discord import app_commands
from discord.ext import commands

from config import tracked_channels
from utils.gemini import (
    tracked_threads,
    context_settings,
    default_settings,
    set_settings_for_context,
)


def get_settings_key_from_interaction(interaction: discord.Interaction):
    """Get the appropriate settings key from an interaction (slash command context)."""
    channel_id = interaction.channel.id
    user_id = interaction.user.id
    
    # Thread context
    if channel_id in tracked_threads:
        return ("thread", channel_id), "this thread"
    
    # DM context
    if isinstance(interaction.channel, discord.DMChannel):
        return ("dm", user_id), "your DMs"
    
    # Tracked channel context
    if channel_id in tracked_channels:
        return ("tracked", user_id), "this tracked channel"
    
    # @mention context
    return ("mention", user_id), "your @mentions"


class Settings(commands.Cog):
    """Cog for AI settings commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='thinking', description='Set the AI thinking level for reasoning depth.')
    @app_commands.choices(level=[
        app_commands.Choice(name='minimal - Fastest, less reasoning', value='minimal'),
        app_commands.Choice(name='low - Fast, simple reasoning', value='low'),
        app_commands.Choice(name='medium - Balanced thinking', value='medium'),
        app_commands.Choice(name='high - Deep reasoning (default)', value='high'),
    ])
    async def thinking(self, interaction: discord.Interaction, level: app_commands.Choice[str]):
        """Set the AI thinking/reasoning level."""
        # Defer the response to prevent timeout
        await interaction.response.defer()
        
        # Get settings key and scope message for this context
        settings_key, scope_msg = get_settings_key_from_interaction(interaction)
        
        # Get current settings or create new ones
        current_settings = context_settings.get(settings_key, default_settings.copy())
        
        # Update thinking level
        current_settings["thinking_level"] = level.value
        set_settings_for_context(settings_key, current_settings)
        
        await interaction.followup.send(f"🧠 Thinking level set to **{level.value}** for {scope_msg}.")
    
    @app_commands.command(name='persona', description='Set a custom persona for the AI.')
    @app_commands.describe(description='The persona description (leave empty or use "default" to reset)')
    async def persona(self, interaction: discord.Interaction, description: str = None):
        """Set a custom persona for the AI."""
        # Get settings key and scope message for this context
        settings_key, scope_msg = get_settings_key_from_interaction(interaction)
        
        # Get current settings or create new ones
        current_settings = context_settings.get(settings_key, default_settings.copy())
        
        # Check if resetting to default
        if description is None or description.lower() == "default":
            current_settings["persona"] = None
            set_settings_for_context(settings_key, current_settings)
            await interaction.response.send_message(f"🎭 Persona reset to default for {scope_msg}.")
        else:
            current_settings["persona"] = description
            set_settings_for_context(settings_key, current_settings)
            await interaction.response.send_message(f"🎭 Persona set for {scope_msg}:\n> {description}")


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Settings(bot))
