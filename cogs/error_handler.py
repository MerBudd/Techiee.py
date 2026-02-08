"""
Error handler cog - Global error handling for app commands.
"""
import discord
from discord import app_commands
from discord.ext import commands


class ErrorHandler(commands.Cog):
    """Global error handler for Discord app commands."""
    
    def __init__(self, bot):
        self.bot = bot
        # Register the error handler
        self.bot.tree.on_error = self.on_app_command_error
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle errors from app commands globally."""
        
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"⏳ This command is on cooldown! Try again in **{error.retry_after:.1f}** seconds.",
                ephemeral=True
            )
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
        elif isinstance(error, app_commands.BotMissingPermissions):
            await interaction.response.send_message(
                "❌ I don't have the required permissions to do that.",
                ephemeral=True
            )
        else:
            # Log unexpected errors
            print(f"⚠️ App command error: {error}")
            # Try to send a generic error message
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ An error occurred while processing this command.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ An error occurred while processing this command.",
                        ephemeral=True
                    )
            except discord.HTTPException:
                pass  # Can't send message, just log it


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(ErrorHandler(bot))
