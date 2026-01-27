"""
Techiee Discord Bot - Main Entry Point

A Discord chatbot powered by Google's Gemini AI models.
Developed by Tech (@techgamerexpert) and Budd (@merbudd).
"""
import discord
from discord.ext import commands
import asyncio

from config import discord_bot_token

# Keep bot running 24/7
from keep_alive import keep_alive
keep_alive()

# --- Discord Bot Setup ---

defaultIntents = discord.Intents.all()
defaultIntents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=defaultIntents,
    help_command=None,
    activity=discord.Activity(
        type=discord.ActivityType.custom,
        name="The best Discord chatbot!"
    )
)

# List of cogs to load - organized by category
COGS = [
    # Processors - content type handlers
    "cogs.processors.text",
    "cogs.processors.images",
    "cogs.processors.videos",
    "cogs.processors.files",
    "cogs.processors.youtube",
    "cogs.processors.websites",
    # Router - message dispatcher (must load after processors)
    "cogs.router",
    # Commands
    "cogs.commands.admin",
    "cogs.commands.general",
    "cogs.commands.settings",
    "cogs.commands.image_gen",
]


async def load_cogs():
    """Load all cogs."""
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"✅ Loaded cog: {cog}")
        except Exception as e:
            print(f"❌ Failed to load cog {cog}: {e}")


@bot.event
async def on_ready():
    """Called when the bot is ready."""
    print(f'Techiee logged in as {bot.user}')


async def main():
    """Main entry point."""
    async with bot:
        await load_cogs()
        await bot.start(discord_bot_token)


# --- Run Bot ---
if __name__ == "__main__":
    asyncio.run(main())
