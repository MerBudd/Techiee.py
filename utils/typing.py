"""
Typing indicator manager for handling concurrent message processing.
Uses reference counting to keep typing active until ALL messages are done.
"""
import asyncio
from collections import defaultdict
import discord


class TypingManager:
    """Manages typing indicators with reference counting per channel.
    
    This ensures that when multiple messages are being processed concurrently,
    the typing indicator stays active until ALL of them are complete.
    """
    
    def __init__(self):
        # {channel_id: count of active processors}
        self._counts = defaultdict(int)
        # {channel_id: typing task}
        self._tasks = {}
        self._locks = defaultdict(asyncio.Lock)
    
    async def start_typing(self, channel: discord.abc.Messageable):
        """Start or increment typing for a channel.
        
        Args:
            channel: Discord channel to show typing indicator in
        """
        async with self._locks[channel.id]:
            self._counts[channel.id] += 1
            
            # Only start a new typing loop if one isn't already running
            if channel.id not in self._tasks or self._tasks[channel.id].done():
                self._tasks[channel.id] = asyncio.create_task(
                    self._typing_loop(channel)
                )
    
    async def stop_typing(self, channel: discord.abc.Messageable):
        """Decrement typing count, stop if no more active processors.
        
        Args:
            channel: Discord channel to stop typing indicator for
        """
        async with self._locks[channel.id]:
            self._counts[channel.id] = max(0, self._counts[channel.id] - 1)
            
            # Only stop typing if there are no more active processors
            if self._counts[channel.id] == 0 and channel.id in self._tasks:
                task = self._tasks.pop(channel.id)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                # Cleanup stale data to prevent memory leak
                self._counts.pop(channel.id, None)
        
        # Cleanup lock outside the lock context (if count is 0)
        if self._counts.get(channel.id, 0) == 0:
            self._locks.pop(channel.id, None)
    
    async def _typing_loop(self, channel: discord.abc.Messageable):
        """Keep sending typing indicator until cancelled.
        
        Discord's typing indicator lasts about 10 seconds, so we refresh
        every 5 seconds to ensure continuous display.
        """
        try:
            while True:
                try:
                    await channel.typing()
                except discord.HTTPException:
                    pass  # Ignore HTTP errors (rate limits, etc.)
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass


# Global instance
typing_manager = TypingManager()
