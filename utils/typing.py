"""
Typing indicator manager for handling concurrent message processing.
Uses Discord's built-in channel.typing() context manager with reference
counting to keep typing active until ALL messages are done.
"""
import asyncio
from collections import defaultdict
import discord


class TypingManager:
    """Manages typing indicators using Discord's channel.typing() context manager.
    
    Uses reference counting so that when multiple messages are being processed
    concurrently, the typing indicator stays active until ALL of them are complete.
    
    The channel.typing() context manager handles the 10-second refresh internally,
    making this far more reliable than manual polling.
    
    Key design: processors call force_stop_immediate() after their final message
    send, so typing stops the instant the response appears in chat.
    """
    
    def __init__(self):
        # {channel_id: set of active message IDs}
        self._active_messages = defaultdict(set)
        # {channel_id: asyncio.Event signaling when count reaches 0}
        self._stop_events = {}
        # {channel_id: the running typing task}
        self._tasks = {}
        self._locks = defaultdict(asyncio.Lock)
        # {channel_id: monotonic timestamp of last keep_alive call}
        self._last_keep_alive = {}
    
    async def start_typing(self, channel: discord.abc.Messageable, message_id: int):
        """Start or increment typing for a channel.
        
        Args:
            channel: Discord channel to show typing indicator in
            message_id: ID of the message being processed
        """
        async with self._locks[channel.id]:
            self._active_messages[channel.id].add(message_id)
            
            # Only start a new typing session if one isn't already running
            if channel.id not in self._tasks or self._tasks[channel.id].done():
                # Create a new stop event
                self._stop_events[channel.id] = asyncio.Event()
                self._tasks[channel.id] = asyncio.create_task(
                    self._typing_session(channel)
                )
    
    async def stop_typing(self, channel: discord.abc.Messageable, message_id: int):
        """Decrement typing count. Typing stops when all processors are done.
        
        Uses a grace period to prevent flicker between consecutive operations.
        
        Args:
            channel: Discord channel to stop typing indicator for
            message_id: ID of the message being processed
        """
        async with self._locks[channel.id]:
            self._active_messages[channel.id].discard(message_id)
            
            if len(self._active_messages[channel.id]) == 0:
                # Signal the typing session to stop (with grace period)
                asyncio.create_task(self._delayed_stop(channel.id))
    
    async def force_stop_immediate(self, channel: discord.abc.Messageable, message_id: int):
        """Force stop typing immediately for this processor.
        
        Decrements the reference count. If the count reaches 0, stops the
        typing indicator instantly without a grace period.
        
        Args:
            channel: Discord channel to stop typing for
            message_id: ID of the message being processed
        """
        async with self._locks[channel.id]:
            self._active_messages[channel.id].discard(message_id)
            
            if len(self._active_messages[channel.id]) == 0:
                event = self._stop_events.get(channel.id)
                if event:
                    event.set()
    
    async def keep_alive(self, channel: discord.abc.Messageable):
        """Reset the grace timer to prevent typing from stopping prematurely.
        
        Call this right before sending a message so that if a delayed_stop
        is pending, it will re-check and see that keep_alive was called
        recently and stay alive.
        
        Args:
            channel: Discord channel to keep typing alive for
        """
        import time
        async with self._locks[channel.id]:
            self._last_keep_alive[channel.id] = time.monotonic()
    
    async def _delayed_stop(self, channel_id: int):
        """Stop typing after a grace period to prevent flicker between messages.
        
        Grace period of 2.0s bridges the gap between API response generation
        and message delivery. If a new processor starts or keep_alive is called
        during the grace period, typing continues.
        """
        import time
        await asyncio.sleep(2.0)
        
        async with self._locks[channel_id]:
            # Re-check: only stop if still at 0 (no new processors started)
            if len(self._active_messages.get(channel_id, set())) == 0:
                # Check if keep_alive was called recently (within last 2s)
                last_alive = self._last_keep_alive.get(channel_id, 0)
                if time.monotonic() - last_alive < 2.0:
                    # Something is still happening, schedule another check
                    asyncio.create_task(self._delayed_stop(channel_id))
                    return
                
                event = self._stop_events.get(channel_id)
                if event:
                    event.set()
    
    async def _typing_session(self, channel: discord.abc.Messageable):
        """Keep typing active using Discord's context manager until stop is signaled.
        
        Discord's channel.typing() context manager automatically sends typing
        indicators and refreshes them every ~10 seconds until the context exits.
        We stay in the context and poll the stop event with simple sleeps.
        """
        stop_event = self._stop_events.get(channel.id)
        if not stop_event:
            return
        
        try:
            async with channel.typing():
                # Stay in the typing context until stop_event is set
                # Simple poll loop — no asyncio.shield or wait_for tricks
                while not stop_event.is_set():
                    await asyncio.sleep(0.3)
        except discord.HTTPException:
            pass  # Channel deleted, forbidden, etc.
        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup stale data
            async with self._locks[channel.id]:
                self._tasks.pop(channel.id, None)
                self._stop_events.pop(channel.id, None)
                self._last_keep_alive.pop(channel.id, None)
                if len(self._active_messages.get(channel.id, set())) == 0:
                    self._active_messages.pop(channel.id, None)
    
    async def force_stop(self, channel: discord.abc.Messageable, message_id: int):
        """Force stop typing immediately for a channel, regardless of ref count.
        
        Legacy alias for force_stop_immediate.
        
        Args:
            channel: Discord channel to force-stop typing for
            message_id: ID of the message being processed
        """
        await self.force_stop_immediate(channel, message_id)

    async def refresh_if_active(self, channel: discord.abc.Messageable):
        """Force a typing API call if typing is supposed to be active.
        
        Discord clears a bot's typing status instantly when the bot sends any message.
        If multiple messages are processing concurrently, sending the first one clears
        typing for the others. This method explicitly sends a new typing request to
        restore it.
        """
        async with self._locks[channel.id]:
            if len(self._active_messages.get(channel.id, set())) > 0 and channel.id in self._tasks:
                try:
                    await channel._state.http.send_typing(channel.id)
                except Exception:
                    pass


# Global instance
typing_manager = TypingManager()
