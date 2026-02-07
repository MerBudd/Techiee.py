"""
Reactions cog - Handles reaction-based actions for bot responses.

Features:
- 🗑️ Delete bot response (original author only)
- 🔄 Regenerate response (original author only)
- Ephemeral rejection message for non-authors
"""
import discord
from discord.ext import commands
import asyncio
from collections import OrderedDict

from utils.helpers import split_and_send_messages


# Maximum number of tracked responses (LRU cache behavior)
MAX_TRACKED_RESPONSES = 1000


class ResponseTracker:
    """Track bot responses with their original message authors and regenerate callbacks."""
    
    def __init__(self, max_size=MAX_TRACKED_RESPONSES):
        self.max_size = max_size
        # {bot_message_id: {"author_id": int, "original_message": Message, "regenerate_callback": callable}}
        self._responses = OrderedDict()
    
    def track(self, bot_message_id: int, author_id: int, original_message, regenerate_callback=None):
        """Track a bot response."""
        # Remove oldest if at capacity
        if len(self._responses) >= self.max_size:
            self._responses.popitem(last=False)
        
        self._responses[bot_message_id] = {
            "author_id": author_id,
            "original_message": original_message,
            "regenerate_callback": regenerate_callback,
        }
    
    def get(self, bot_message_id: int):
        """Get tracking info for a bot message."""
        return self._responses.get(bot_message_id)
    
    def remove(self, bot_message_id: int):
        """Remove a tracked response."""
        self._responses.pop(bot_message_id, None)


# Global tracker instance
response_tracker = ResponseTracker()


class Reactions(commands.Cog):
    """Cog for handling reaction-based actions."""
    
    DELETE_EMOJI = "🗑️"
    REGENERATE_EMOJI = "🔄"
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reaction adds for delete and regenerate actions."""
        # Ignore bot's own reactions
        if payload.user_id == self.bot.user.id:
            return
        
        emoji = str(payload.emoji)
        if emoji not in (self.DELETE_EMOJI, self.REGENERATE_EMOJI):
            return
        
        # Check if this is a tracked bot response
        tracking_info = response_tracker.get(payload.message_id)
        if not tracking_info:
            return
        
        # Get the channel and message
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except discord.NotFound:
                return
        
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            response_tracker.remove(payload.message_id)
            return
        
        # Check if the reactor is the original author
        if payload.user_id != tracking_info["author_id"]:
            # Remove their reaction
            try:
                user = await self.bot.fetch_user(payload.user_id)
                await message.remove_reaction(payload.emoji, user)
            except (discord.NotFound, discord.Forbidden):
                pass
            
            # Send ephemeral-like message (delete after a few seconds)
            try:
                warning = await channel.send(
                    f"<@{payload.user_id}> Only the original author can use this reaction.",
                    delete_after=5.0
                )
            except discord.Forbidden:
                pass
            return
        
        # Handle the action
        if emoji == self.DELETE_EMOJI:
            await self._handle_delete(message, tracking_info)
        elif emoji == self.REGENERATE_EMOJI:
            await self._handle_regenerate(message, tracking_info, channel)
    
    async def _handle_delete(self, message: discord.Message, tracking_info: dict):
        """Delete the bot's response."""
        try:
            await message.delete()
            response_tracker.remove(message.id)
        except discord.Forbidden:
            pass
        except discord.NotFound:
            response_tracker.remove(message.id)
    
    async def _handle_regenerate(self, message: discord.Message, tracking_info: dict, channel):
        """Regenerate the bot's response."""
        regenerate_callback = tracking_info.get("regenerate_callback")
        original_message = tracking_info.get("original_message")
        
        if not regenerate_callback or not original_message:
            return
        
        # Remove the regenerate reaction (show we're processing)
        try:
            await message.remove_reaction(self.REGENERATE_EMOJI, self.bot.user)
        except (discord.NotFound, discord.Forbidden):
            pass
        
        # Show typing indicator
        async with channel.typing():
            try:
                # Call regenerate callback to get new response
                new_response = await regenerate_callback()
                
                # Delete old message
                try:
                    await message.delete()
                    response_tracker.remove(message.id)
                except discord.NotFound:
                    pass
                
                # Send new response
                await split_and_send_messages(
                    original_message,
                    new_response,
                    1900,
                    original_message.author.id
                )
            except Exception as e:
                # If regeneration fails, notify the user
                try:
                    await channel.send(
                        f"❌ Failed to regenerate response: {str(e)[:100]}",
                        delete_after=10.0
                    )
                except discord.Forbidden:
                    pass


async def add_reaction_buttons(message: discord.Message):
    """Add delete and regenerate reaction buttons to a message."""
    try:
        await message.add_reaction(Reactions.DELETE_EMOJI)
        await message.add_reaction(Reactions.REGENERATE_EMOJI)
    except (discord.Forbidden, discord.NotFound):
        pass


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Reactions(bot))
