"""
Admin commands cog - Owner-only commands.
"""
import discord
from discord import app_commands
from discord.ext import commands

from config import discord_admin_ids


class Admin(commands.Cog):
    """Cog for admin-only commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='sync', description='Sync slash commands globally. Admin only.')
    async def sync(self, interaction: discord.Interaction):
        """Sync slash commands globally (admin only)."""
        if interaction.user.id in discord_admin_ids:
            await interaction.response.defer(ephemeral=True)  # Defer since sync can take a moment
            
            # Sync globally
            synced = await self.bot.tree.sync()
            
            print(f'Command tree synced. Synced {len(synced)} commands globally.')
            await interaction.followup.send(f'✅ Command tree synced! Synced {len(synced)} commands globally.\n-# Note: Global sync can take up to 1 hour to fully propagate across Discord.')
        else:
            await interaction.response.send_message('❌ You must be an admin to use this command!', ephemeral=True)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Admin(bot))
