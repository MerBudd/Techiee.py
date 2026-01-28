"""
Retry utilities for handling 503 server overload errors from Gemini API.
"""
import asyncio
import discord
from discord import ui

from utils.helpers import split_and_send_messages


def is_503_error(response_text):
    """Check if the response text indicates a 503 server overload error.
    
    Args:
        response_text: The response text from the Gemini API
    
    Returns:
        True if this is a 503 error, False otherwise
    """
    if not response_text:
        return False
    return "503" in response_text and "UNAVAILABLE" in response_text


class RetryButton(ui.Button):
    """A retry button with countdown functionality."""
    
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="🔄 Retry in 3s",
            disabled=True
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click - trigger retry."""
        # Disable the button and show retrying state
        self.disabled = True
        self.label = "🔄 Retrying..."
        await interaction.response.edit_message(view=self.view)
        
        # Trigger the retry via the view
        await self.view.do_retry(interaction)


class RetryView(ui.View):
    """A view with a retry button for 503 errors.
    
    Features:
    - 3-second countdown before button becomes active
    - Only the original message author can click
    - Tracks retry count and updates message on failures
    - Deletes error message and sends success response normally
    """
    
    def __init__(self, author_id, original_message, retry_callback, update_history_callback=None, max_retries=5, timeout=120):
        """Initialize the retry view.
        
        Args:
            author_id: Discord user ID of the original message author
            original_message: The original Discord message to reply to
            retry_callback: Async function to call on retry that returns response_text
            update_history_callback: Optional async function to update history on success
            max_retries: Maximum number of retry attempts
            timeout: View timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.original_message = original_message
        self.retry_callback = retry_callback
        self.update_history_callback = update_history_callback
        self.max_retries = max_retries
        self.retry_count = 0
        self.error_message = None  # Will be set after sending
        
        # Add the retry button
        self.retry_button = RetryButton()
        self.add_item(self.retry_button)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the original author can interact with the view."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Only the original author can retry this request.",
                ephemeral=True
            )
            return False
        return True
    
    async def start_countdown(self):
        """Start the countdown timer for the retry button."""
        for seconds in range(3, 0, -1):
            self.retry_button.label = f"🔄 Retry in {seconds}s"
            if self.error_message:
                try:
                    await self.error_message.edit(view=self)
                except discord.NotFound:
                    return  # Message was deleted
            await asyncio.sleep(1)
        
        # Enable the button
        self.retry_button.disabled = False
        self.retry_button.label = "🔄 Retry"
        if self.error_message:
            try:
                await self.error_message.edit(view=self)
            except discord.NotFound:
                pass  # Message was deleted
    
    async def do_retry(self, interaction: discord.Interaction):
        """Perform the retry operation."""
        self.retry_count += 1
        
        # Call the retry callback
        response_text = await self.retry_callback()
        
        # Check if still a 503 error
        if is_503_error(response_text):
            if self.retry_count >= self.max_retries:
                # Max retries reached
                self.retry_button.label = "❌ Max retries reached"
                self.retry_button.disabled = True
                self.retry_button.style = discord.ButtonStyle.danger
                try:
                    await self.error_message.edit(
                        content=f"❌ Retry failed {self.retry_count} times. Maximum retries reached. Please try again later.",
                        view=self
                    )
                except discord.NotFound:
                    pass
            else:
                # Still failing, update message and restart countdown
                try:
                    self.retry_button.disabled = True
                    self.retry_button.label = "🔄 Retry in 3s"
                    await self.error_message.edit(
                        content=f"❌ Retry failed {self.retry_count} time{'s' if self.retry_count > 1 else ''}. Please try again.\n\n*The server is still overloaded.*",
                        view=self
                    )
                    # Start countdown again
                    asyncio.create_task(self.start_countdown())
                except discord.NotFound:
                    pass
        else:
            # Success! Delete error message and send response normally
            try:
                await self.error_message.delete()
            except discord.NotFound:
                pass  # Already deleted
            
            # Call history update callback if provided
            if self.update_history_callback:
                await self.update_history_callback(response_text)
            
            # Send the successful response
            await split_and_send_messages(
                self.original_message, 
                response_text, 
                1900, 
                self.original_message.author.id
            )
            
            # Stop the view
            self.stop()
    
    async def on_timeout(self):
        """Handle view timeout - disable the button."""
        self.retry_button.disabled = True
        self.retry_button.label = "⏱️ Timed out"
        self.retry_button.style = discord.ButtonStyle.secondary
        if self.error_message:
            try:
                await self.error_message.edit(view=self)
            except discord.NotFound:
                pass


async def send_response_with_retry(message, response_text, retry_callback, update_history_callback=None):
    """Send a response, showing a retry button if it's a 503 error.
    
    Args:
        message: The original Discord message to reply to
        response_text: The response text from Gemini API
        retry_callback: Async function to call on retry that returns new response_text
        update_history_callback: Optional async function to call on success with the response_text
    
    Returns:
        True if response was sent successfully (either initially or after retry flow started),
        False if there was an issue.
    """
    if is_503_error(response_text):
        # Create retry view
        view = RetryView(
            author_id=message.author.id,
            original_message=message,
            retry_callback=retry_callback,
            update_history_callback=update_history_callback
        )
        
        # Send error message with retry button
        error_msg = await message.reply(
            "❌ The server is overloaded. Please wait and retry.\n\n*A retry button will be available shortly.*",
            view=view,
            mention_author=True
        )
        
        # Store reference to error message in view
        view.error_message = error_msg
        
        # Start countdown in background
        asyncio.create_task(view.start_countdown())
        
        return True
    else:
        # Not a 503 error, update history and send normally
        if update_history_callback:
            await update_history_callback(response_text)
        
        await split_and_send_messages(message, response_text, 1900, message.author.id)
        return True
