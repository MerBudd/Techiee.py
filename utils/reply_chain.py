"""
Reply chain context utility - Fetches Discord reply chain for context.

When a user replies to a message, this utility fetches the parent messages
in the reply chain to provide conversation context to Gemini.
"""
import discord
from datetime import datetime

from google.genai.types import Part, Content


async def fetch_reply_chain(message: discord.Message, max_depth: int = 10) -> list:
    """Fetch the reply chain for a message.
    
    Walks up the reply chain, collecting parent messages with their
    timestamps, display names, and usernames.
    
    Args:
        message: The Discord message to start from
        max_depth: Maximum number of parent messages to fetch (default 10)
    
    Returns:
        List of Content objects for Gemini, oldest first.
        Returns empty list if the message is not a reply.
    """
    if not message.reference:
        return []
    
    chain_messages = []
    current = message
    depth = 0
    
    while current.reference and depth < max_depth:
        try:
            # Fetch the parent message
            parent_msg = await current.channel.fetch_message(current.reference.message_id)
            chain_messages.append(parent_msg)
            current = parent_msg
            depth += 1
        except (discord.NotFound, discord.HTTPException):
            # Parent message was deleted or inaccessible
            break
    
    if not chain_messages:
        return []
    
    # Reverse to get oldest first
    chain_messages.reverse()
    
    # Convert to Gemini Content objects (now async for image downloads)
    contents = []
    for msg in chain_messages:
        content = await format_message_for_context(msg)
        if content:
            contents.append(content)
    
    return contents


async def format_message_for_context(message: discord.Message) -> Content:
    """Format a Discord message as a Gemini Content object.
    
    Downloads and includes actual image attachments so Gemini can see them.
    
    Args:
        message: The Discord message to format
    
    Returns:
        Content object with message info and attachments, or None if empty message.
    """
    import aiohttp
    from google.genai.types import Part
    
    # Build the context text with metadata
    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    display_name = message.author.display_name
    username = message.author.name
    
    parts = []
    
    # Distinguish bot vs user messages
    if message.author.bot:
        # Bot/assistant messages
        text = message.content if message.content else "[No text content]"
        parts.append(Part(text=f"[{timestamp}]\n{text}"))
        
        # For bot messages, just note attachments (don't download)
        if message.attachments:
            attachment_info = ", ".join([f"[Sent attachment: {a.filename}]" for a in message.attachments])
            parts.append(Part(text=attachment_info))
        
        return Content(role="model", parts=parts)
    else:
        # User messages
        text = message.content if message.content else "[No text content]"
        formatted_text = f"[{timestamp}] {display_name} (@{username}):\n{text}"
        parts.append(Part(text=formatted_text))
        
        # Download and include images/attachments
        if message.attachments:
            async with aiohttp.ClientSession() as session:
                for attachment in message.attachments:
                    # Check if it's an image
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        try:
                            async with session.get(attachment.url) as resp:
                                if resp.status == 200:
                                    image_bytes = await resp.read()
                                    parts.append(Part(inline_data={
                                        "mime_type": attachment.content_type,
                                        "data": image_bytes
                                    }))
                        except Exception as e:
                            # If download fails, just note the filename
                            parts.append(Part(text=f"[Failed to load image: {attachment.filename}]"))
                    else:
                        # Non-image attachments: just note the filename
                        parts.append(Part(text=f"[Attachment: {attachment.filename}]"))
        
        return Content(role="user", parts=parts)


def format_reply_chain_as_context_text(chain_contents: list) -> str:
    """Format reply chain contents as a context text block.
    
    This is useful for prepending to the user's current message
    when the chain should be included as part of the current turn.
    
    Args:
        chain_contents: List of Content objects from fetch_reply_chain
    
    Returns:
        Formatted context string, or empty string if no chain.
    """
    if not chain_contents:
        return ""
    
    context_parts = []
    context_parts.append("--- Reply Chain Context ---")
    
    for content in chain_contents:
        if content.parts:
            for part in content.parts:
                if hasattr(part, 'text') and part.text:
                    role_indicator = "[Bot]" if content.role == "model" else "[User]"
                    context_parts.append(f"{role_indicator} {part.text}")
    
    context_parts.append("--- End Reply Chain ---\n")
    
    return "\n".join(context_parts)
