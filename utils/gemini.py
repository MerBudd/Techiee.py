"""
Gemini AI client and response generation functions.
"""
import asyncio
import aiohttp
import tempfile
import os

from google import genai
from google.genai import types
from google.genai.types import Part, Content

from config import (
    gemini_api_key,
    gemini_model,
    image_model,
    system_instruction,
    default_image_prompt,
    default_pdf_and_txt_prompt,
    default_url_prompt,
    default_aspect_ratio,
    url_context_tool,
    safety_settings,
    create_generate_config,
    tracked_channels,
    max_history,
)

# --- Gemini Client Setup ---
client = genai.Client(api_key=gemini_api_key)

# --- Shared State ---
message_history = {}
tracked_threads = []

# Per-user settings (for DMs and tracked channels)
user_settings = {}

# Per-thread settings (for created threads - applies to all users in that thread)
thread_settings = {}

# Default settings
default_settings = {
    "thinking_level": "minimal",  # minimal, low, medium, high
    "persona": None  # Custom persona, None means use default system instruction
}


# --- Settings Management ---

def get_settings(message):
    """Get settings for the current context (user or thread)."""
    if message.channel.id in tracked_threads:
        return thread_settings.get(message.channel.id, default_settings.copy())
    else:
        return user_settings.get(message.author.id, default_settings.copy())


def set_settings(context_id, is_thread, settings):
    """Set settings for a user or thread."""
    if is_thread:
        thread_settings[context_id] = settings
    else:
        user_settings[context_id] = settings


def get_effective_system_instruction(settings):
    """Get the system instruction with persona applied if set."""
    if settings.get("persona"):
        return f"{settings['persona']}\n\n{system_instruction}"
    return system_instruction


# --- File Processing Utilities ---

async def wait_for_file_active(uploaded_file, max_wait_seconds=120, poll_interval=2):
    """Wait for a file to become ACTIVE after upload.
    
    Video files often need processing time before they can be used.
    Returns the file when active, or raises an exception on timeout.
    """
    import time
    start_time = time.time()
    
    while True:
        # Check if file is active - run in thread to not block event loop
        file_info = await asyncio.to_thread(client.files.get, name=uploaded_file.name)
        if file_info.state.name == "ACTIVE":
            return file_info
        elif file_info.state.name == "FAILED":
            raise Exception(f"File processing failed: {uploaded_file.name}")
        
        # Check timeout
        elapsed = time.time() - start_time
        if elapsed >= max_wait_seconds:
            raise Exception(f"File processing timed out after {max_wait_seconds} seconds. Please try with a shorter video.")
        
        # Wait before next poll
        await asyncio.sleep(poll_interval)


# --- Message History ---
# History now stores Content objects to support multimodal conversations
# Each Content has a role ("user" or "model") and a list of Parts

def update_message_history(user_id, content):
    """Update message history with a Content object.
    
    Args:
        user_id: The user's ID
        content: A Content object (with role and parts)
    """
    if content is None:
        return
    if user_id in message_history:
        message_history[user_id].append(content)
        if len(message_history[user_id]) > max_history:
            message_history[user_id].pop(0)
    else:
        message_history[user_id] = [content]


def get_message_history_contents(user_id):
    """Get message history as a list of Content objects for Gemini API.
    
    Returns:
        List of Content objects, or empty list if no history.
    """
    return message_history.get(user_id, [])


def create_user_content(parts):
    """Create a user Content object from parts.
    
    Args:
        parts: A list of Part objects (text, image, file, etc.)
    
    Returns:
        Content object with role="user"
    """
    return Content(role="user", parts=parts)


def create_model_content(text):
    """Create a model Content object from text response.
    
    Args:
        text: The model's text response
    
    Returns:
        Content object with role="model"
    """
    if text is None:
        return None
    return Content(role="model", parts=[Part(text=text)])


# --- Response Generation Functions ---

async def generate_response_with_text(contents, settings):
    """Generate a response for text input with optional history.
    
    Args:
        contents: Either a string (single message) or list of Content objects (with history)
        settings: User/thread settings dict
    
    Returns:
        Response text string
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        # Include google_search_tool if you have billing setup - model automatically decides when to search
        # Run in thread to prevent blocking the event loop (keeps typing indicator alive)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=gemini_model,
            contents=contents,
            config=create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
                # tools=[google_search_tool], # Requires paid plan
            )
        )
        # Handle case where response.text is None
        if response.text is None:
            return "❌ I received an empty response. Please try again."
        return response.text
    except Exception as e:
        return "❌ Exception: " + str(e)


async def process_image_attachment(attachment, user_text, settings, history=None):
    """Process an image attachment using the Files API with optional history.
    
    Args:
        attachment: Discord attachment object
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
    
    Returns:
        Tuple of (response_text, user_content_parts, uploaded_file) for history tracking
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status != 200:
                    return ("❌ Unable to download the image.", None, None)
                image_data = await resp.read()
        
        # Create a temporary file and upload to Gemini
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.filename)[1]) as tmp_file:
            tmp_file.write(image_data)
            tmp_path = tmp_file.name
        
        try:
            # Upload file to Gemini - run in thread to not block event loop
            uploaded_file = await asyncio.to_thread(client.files.upload, file=tmp_path)
            
            prompt = user_text if user_text else default_image_prompt
            
            # Build user content parts for this message
            user_parts = [
                Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
                Part(text=prompt)
            ]
            
            # Build contents: history + current message
            if history:
                contents = history + [Content(role="user", parts=user_parts)]
            else:
                contents = user_parts
            
            # Run in thread to prevent blocking the event loop (keeps typing indicator alive)
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=gemini_model,
                contents=contents,
                config=create_generate_config(
                    system_instruction=effective_system_instruction,
                    thinking_level=thinking_level,
                )
            )
            return (response.text, user_parts, uploaded_file)
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return ("❌ Exception: " + str(e), None, None)


async def process_video_attachment(attachment, user_text, settings, history=None):
    """Process a video attachment using the Files API with proper state waiting.
    
    Args:
        attachment: Discord attachment object
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
    
    Returns:
        Tuple of (response_text, user_content_parts, uploaded_file) for history tracking
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        # Download the video
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status != 200:
                    return ("❌ Unable to download the video.", None, None)
                video_data = await resp.read()
        
        # Create a temporary file and upload to Gemini
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.filename)[1]) as tmp_file:
            tmp_file.write(video_data)
            tmp_path = tmp_file.name
        
        try:
            # Upload file to Gemini - run in thread to not block event loop
            uploaded_file = await asyncio.to_thread(client.files.upload, file=tmp_path)
            
            # Wait for video file to become ACTIVE (videos need processing time)
            print(f"Waiting for video file to become active: {uploaded_file.name}")
            active_file = await wait_for_file_active(uploaded_file)
            print(f"Video file is now active: {active_file.name}")
            
            prompt = user_text if user_text else "What is this video about? Summarize it for me."
            
            # Build user content parts for this message
            user_parts = [
                Part.from_uri(file_uri=active_file.uri, mime_type=active_file.mime_type),
                Part(text=prompt)
            ]
            
            # Build contents: history + current message
            if history:
                contents = history + [Content(role="user", parts=user_parts)]
            else:
                contents = user_parts
            
            # Run in thread to prevent blocking the event loop (keeps typing indicator alive)
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=gemini_model,
                contents=contents,
                config=create_generate_config(
                    system_instruction=effective_system_instruction,
                    thinking_level=thinking_level,
                )
            )
            return (response.text, user_parts, active_file)
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return ("❌ Exception: " + str(e), None, None)


async def process_file_attachment(attachment, user_text, settings, history=None):
    """Process PDF or text file attachments using the Files API.
    
    Args:
        attachment: Discord attachment object
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
    
    Returns:
        Tuple of (response_text, user_content_parts, uploaded_file) for history tracking
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status != 200:
                    return ("❌ Unable to download the attachment.", None, None)
                file_data = await resp.read()
        
        # Create a temporary file and upload to Gemini
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.filename)[1]) as tmp_file:
            tmp_file.write(file_data)
            tmp_path = tmp_file.name
        
        try:
            # Upload file to Gemini - run in thread to not block event loop
            uploaded_file = await asyncio.to_thread(client.files.upload, file=tmp_path)
            
            prompt = user_text if user_text else default_pdf_and_txt_prompt
            
            # Build user content parts for this message
            user_parts = [
                Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
                Part(text=prompt)
            ]
            
            # Build contents: history + current message
            if history:
                contents = history + [Content(role="user", parts=user_parts)]
            else:
                contents = user_parts
            
            # Run in thread to prevent blocking the event loop (keeps typing indicator alive)
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=gemini_model,
                contents=contents,
                config=create_generate_config(
                    system_instruction=effective_system_instruction,
                    thinking_level=thinking_level,
                )
            )
            return (response.text, user_parts, uploaded_file)
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return ("❌ Exception: " + str(e), None, None)


async def process_youtube_url(url, user_text, settings, history=None):
    """Process YouTube video URL using FileData.
    
    Args:
        url: YouTube URL
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
    
    Returns:
        Tuple of (response_text, user_content_parts) for history tracking
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        prompt = user_text.replace(url, "").strip() if user_text else default_url_prompt
        
        # Build user content parts for this message
        user_parts = [
            Part(file_data=types.FileData(file_uri=url)),
            Part(text=prompt)
        ]
        
        # Build contents: history + current message
        if history:
            contents = history + [Content(role="user", parts=user_parts)]
        else:
            contents = Content(role="user", parts=user_parts)
        
        # Run in thread to prevent blocking the event loop (keeps typing indicator alive)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=gemini_model,
            contents=contents,
            config=create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
            )
        )
        return (response.text, user_parts)
    except Exception as e:
        return ("❌ Exception: " + str(e), None)


async def process_website_url(url, user_text, settings, history=None):
    """Process website URL using URL context tool.
    
    Args:
        url: Website URL
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
    
    Returns:
        Tuple of (response_text, user_content_parts) for history tracking
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        prompt = user_text if user_text else f"{default_url_prompt} {url}"
        
        # If user provided custom text, make sure the URL is included
        if user_text and url not in user_text:
            prompt = f"{user_text} {url}"
        
        # Build user content parts for this message
        user_parts = [Part(text=prompt)]
        
        # Build contents: history + current message
        if history:
            contents = history + [Content(role="user", parts=user_parts)]
        else:
            contents = prompt  # URL context tool works with string
        
        # Run in thread to prevent blocking the event loop (keeps typing indicator alive)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=gemini_model,
            contents=contents,
            config=create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
                tools=[url_context_tool],
            )
        )
        return (response.text, user_parts)
    except Exception as e:
        return ("❌ Exception: " + str(e), None)


async def generate_or_edit_image(prompt, images=None, aspect_ratio=None):
    """Generate or edit images using Nano Banana (gemini-2.5-flash-image).
    
    Args:
        prompt: Text prompt for generation/editing
        images: List of image byte tuples [(bytes, mime_type), ...] (optional, for editing)
        aspect_ratio: Aspect ratio string like "16:9" (optional)
    
    Returns:
        Tuple of (text_response, image_bytes, mime_type) or (error_message, None, None)
    """
    from google.genai.types import Part, GenerateContentConfig, ImageConfig
    
    try:
        # Build contents list with prompt and any input images
        contents = []
        
        # Add input images first if provided
        if images:
            for img_bytes, mime_type in images:
                import base64
                b64_data = base64.b64encode(img_bytes).decode('utf-8')
                contents.append(Part.from_bytes(data=img_bytes, mime_type=mime_type))
        
        # Add the text prompt
        contents.append(prompt)
        
        # Build config with aspect ratio
        config_kwargs = {
            "response_modalities": ["Text", "Image"],
            "safety_settings": safety_settings,
        }
        
        # Add aspect ratio if specified
        if aspect_ratio:
            config_kwargs["image_config"] = ImageConfig(aspect_ratio=aspect_ratio)
        elif default_aspect_ratio:
            config_kwargs["image_config"] = ImageConfig(aspect_ratio=default_aspect_ratio)
        
        config = GenerateContentConfig(**config_kwargs)
        
        # Generate content - run in thread to not block event loop
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=image_model,
            contents=contents,
            config=config
        )
        
        # Extract text and image from response
        text_response = None
        image_bytes = None
        image_mime_type = None
        
        for part in response.parts:
            if part.text is not None:
                text_response = part.text
            elif part.inline_data is not None:
                image_bytes = part.inline_data.data
                image_mime_type = part.inline_data.mime_type
        
        return (text_response, image_bytes, image_mime_type)
        
    except Exception as e:
        return (f"❌ Exception: {str(e)}", None, None)
