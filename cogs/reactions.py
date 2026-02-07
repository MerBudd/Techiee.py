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
        # {bot_message_id: tracking_info_dict}
        self._responses = OrderedDict()
    
    def track(self, bot_message_id: int, author_id: int, original_message, regenerate_callback=None, all_message_ids=None, history_key=None):
        """Track a bot response.
        
        Args:
            bot_message_id: The message ID to track (usually the last split)
            author_id: Discord user ID of the original author
            original_message: The original Discord message object
            regenerate_callback: Async function to regenerate the response
            all_message_ids: List of all split message IDs (for multi-message responses)
            history_key: Tuple key for message_history (for updating history on delete/regenerate)
        """
        # Remove oldest if at capacity
        if len(self._responses) >= self.max_size:
            self._responses.popitem(last=False)
        
        self._responses[bot_message_id] = {
            "author_id": author_id,
            "original_message": original_message,
            "regenerate_callback": regenerate_callback,
            "all_message_ids": all_message_ids or [bot_message_id],
            "history_key": history_key,
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
        """Delete the bot's response (all splits) and update history."""
        from utils.gemini import message_history
        
        # Get all message IDs for this response (handles split messages)
        all_message_ids = tracking_info.get("all_message_ids", [message.id])
        history_key = tracking_info.get("history_key")
        
        # Delete all split messages
        channel = message.channel
        for msg_id in all_message_ids:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        
        # Remove from tracker
        response_tracker.remove(message.id)
        
        # Update history: remove the last model response
        if history_key and history_key in message_history:
            history = message_history[history_key]
            # Find and remove the last model response
            for i in range(len(history) - 1, -1, -1):
                if history[i].role == "model":
                    history.pop(i)
                    break

    
    async def _handle_regenerate(self, message: discord.Message, tracking_info: dict, channel):
        """Regenerate the bot's response (deletes all splits, updates history)."""
        from utils.gemini import message_history
        from utils.retry import split_and_send_messages_with_tracking
        
        regenerate_callback = tracking_info.get("regenerate_callback")
        original_message = tracking_info.get("original_message")
        all_message_ids = tracking_info.get("all_message_ids", [message.id])
        history_key = tracking_info.get("history_key")
        
        if not regenerate_callback or not original_message:
            return
        
        # Remove the regenerate reaction (show we're processing)
        try:
            await message.remove_reaction(self.REGENERATE_EMOJI, self.bot.user)
        except (discord.NotFound, discord.Forbidden):
            pass
        
        try:
            # Show typing indicator while generating
            new_response = None
            async with channel.typing():
                # Call regenerate callback to get new response
                new_response = await regenerate_callback()
            
            # Delete all old split messages (AFTER typing ends)
            for msg_id in all_message_ids:
                try:
                    msg = await channel.fetch_message(msg_id)
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
            
            response_tracker.remove(message.id)
            
            # Update history: remove old model response, add new one
            if history_key and history_key in message_history:
                history = message_history[history_key]
                # Find and remove the last model response
                for i in range(len(history) - 1, -1, -1):
                    if history[i].role == "model":
                        history.pop(i)
                        break
            
            # Send new response (outside typing block to stop indicator)
            from cogs.reactions import add_reaction_buttons
            sent_messages = await split_and_send_messages_with_tracking(
                original_message,
                new_response,
                1900,
                original_message.author.id
            )
            
            # Track new response and add reactions to last split only
            if sent_messages:
                all_ids = [m.id for m in sent_messages]
                last_msg = sent_messages[-1]
                response_tracker.track(
                    bot_message_id=last_msg.id,
                    author_id=original_message.author.id,
                    original_message=original_message,
                    regenerate_callback=regenerate_callback,
                    all_message_ids=all_ids,
                    history_key=history_key
                )
                await add_reaction_buttons(last_msg)
                
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
