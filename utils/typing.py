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
    """
    
    def __init__(self):
        # {channel_id: count of active processors}
        self._counts = defaultdict(int)
        # {channel_id: asyncio.Event signaling when count reaches 0}
        self._stop_events = {}
        # {channel_id: the running typing task}
        self._tasks = {}
        self._locks = defaultdict(asyncio.Lock)
    
    async def start_typing(self, channel: discord.abc.Messageable):
        """Start or increment typing for a channel.
        
        Args:
            channel: Discord channel to show typing indicator in
        """
        async with self._locks[channel.id]:
            self._counts[channel.id] += 1
            
            # Only start a new typing session if one isn't already running
            if channel.id not in self._tasks or self._tasks[channel.id].done():
                # Create a new stop event
                self._stop_events[channel.id] = asyncio.Event()
                self._tasks[channel.id] = asyncio.create_task(
                    self._typing_session(channel)
                )
    
    async def stop_typing(self, channel: discord.abc.Messageable):
        """Decrement typing count. Typing stops when all processors are done.
        
        Args:
            channel: Discord channel to stop typing indicator for
        """
        async with self._locks[channel.id]:
            self._counts[channel.id] = max(0, self._counts[channel.id] - 1)
            
            if self._counts[channel.id] == 0:
                # Signal the typing session to stop (with a small grace period)
                asyncio.create_task(self._delayed_stop(channel.id))
    
    async def _delayed_stop(self, channel_id: int):
        """Stop typing after a brief grace period to prevent flicker between messages."""
        await asyncio.sleep(0.5)
        
        async with self._locks[channel_id]:
            # Re-check: only stop if still at 0 (no new processors started)
            if self._counts.get(channel_id, 0) == 0:
                event = self._stop_events.get(channel_id)
                if event:
                    event.set()
    
    async def _typing_session(self, channel: discord.abc.Messageable):
        """Keep typing active using Discord's context manager until stop is signaled.
        
        Discord's channel.typing() context manager automatically sends typing
        indicators and refreshes them every ~10 seconds until the context exits.
        We wrap this in a loop that checks our stop event periodically.
        """
        stop_event = self._stop_events.get(channel.id)
        if not stop_event:
            return
        
        try:
            async with channel.typing():
                # Stay in the typing context until stop_event is set
                # Check frequently so we exit promptly when done
                while not stop_event.is_set():
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(stop_event.wait()),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue  # Keep typing
        except discord.HTTPException:
            pass  # Channel deleted, forbidden, etc.
        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup stale data
            async with self._locks[channel.id]:
                self._tasks.pop(channel.id, None)
                self._stop_events.pop(channel.id, None)
                if self._counts.get(channel.id, 0) == 0:
                    self._counts.pop(channel.id, None)
    
    async def force_stop(self, channel: discord.abc.Messageable):
        """Force stop typing immediately for a channel, regardless of ref count.
        
        Args:
            channel: Discord channel to force-stop typing for
        """
        async with self._locks[channel.id]:
            self._counts[channel.id] = 0
            event = self._stop_events.get(channel.id)
            if event:
                event.set()


# Global instance
typing_manager = TypingManager()
