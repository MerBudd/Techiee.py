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
    Also extracts stickers, GIFs, and embed content.
    
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
        
        # Include embed content for bot messages too
        _add_embed_parts(message, parts)
        
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
        
        # Stickers
        _add_sticker_parts(message, parts)
        
        # GIFs and embeds
        _add_embed_parts(message, parts)
        
        return Content(role="user", parts=parts)


def _add_sticker_parts(message: discord.Message, parts: list):
    """Extract sticker info from a message and add as text parts."""
    from google.genai.types import Part
    
    if message.stickers:
        for sticker in message.stickers:
            sticker_text = f"[Sticker: {sticker.name}]"
            if hasattr(sticker, 'url') and sticker.url:
                sticker_text += f" (URL: {sticker.url})"
            parts.append(Part(text=sticker_text))


def _add_embed_parts(message: discord.Message, parts: list):
    """Extract embed content (rich embeds, GIFs, etc.) from a message and add as text parts."""
    from google.genai.types import Part
    
    if message.embeds:
        for embed in message.embeds:
            # Check for GIF embeds (Tenor, Giphy)
            if embed.type == "gifv" or (embed.provider and embed.provider.name and embed.provider.name.lower() in ("tenor", "giphy")):
                gif_url = embed.url or embed.thumbnail.url if embed.thumbnail else None
                if gif_url:
                    parts.append(Part(text=f"[GIF: {gif_url}]"))
                continue
            
            # Rich embeds: extract title, description, fields, footer
            embed_lines = []
            if embed.title:
                embed_lines.append(f"Title: {embed.title}")
            if embed.author and embed.author.name:
                embed_lines.append(f"Author: {embed.author.name}")
            if embed.description:
                embed_lines.append(f"Description: {embed.description}")
            if embed.fields:
                for field in embed.fields:
                    embed_lines.append(f"{field.name}: {field.value}")
            if embed.footer and embed.footer.text:
                embed_lines.append(f"Footer: {embed.footer.text}")
            if embed.url:
                embed_lines.append(f"URL: {embed.url}")
            
            if embed_lines:
                parts.append(Part(text=f"[Embed]\n" + "\n".join(embed_lines) + "\n[/Embed]"))


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
