"""
General commands cog - User-accessible general commands.
"""
import discord
from discord import app_commands
from discord.ext import commands

from config import help_text
from utils.gemini import tracked_threads, message_history


class General(commands.Cog):
    """Cog for general user commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='help', description='Shows help(ful) info and commands for Techiee.')
    async def help(self, interaction: discord.Interaction):
        # Display help information.
        await interaction.response.send_message(help_text)
    
    @app_commands.command(name='createthread', description='Create a thread in which Techiee will respond to every message.')
    async def create_thread(self, interaction: discord.Interaction, name: str):
        # Create a tracked thread for bot conversations.
        try:
            thread = await interaction.channel.create_thread(name=name, auto_archive_duration=60)
            tracked_threads.append(thread.id)
            await interaction.response.send_message(f"Thread '{name}' created! Go to <#{thread.id}> to join the thread and chat with me there.")
        except Exception as e:
            await interaction.response.send_message("❗️ Error creating thread!")
    
    @app_commands.command(name='forget', description='Clear your message history with Techiee.')
    async def forget(self, interaction: discord.Interaction):
        # Clear the user's message history.
        user_id = interaction.user.id
        if user_id in message_history:
            del message_history[user_id]
            await interaction.response.send_message(f"🧼 History cleared for {interaction.user.name}!")
        else:
            await interaction.response.send_message("📭 You don't have any history to clear.")


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(General(bot))
