"""
Gemini AI client and response generation functions.
"""
import asyncio
import aiohttp
import tempfile
import os

from utils.helpers import convert_latex_to_discord

from google import genai
from google.genai import types
from google.genai.types import Part, Content

from config import (
    gemini_api_key,
    gemini_api_keys,
    gemini_model,
    image_model,
    get_system_instruction,
    default_image_prompt,
    default_pdf_and_txt_prompt,
    default_url_prompt,
    default_aspect_ratio,
    url_context_tool,
    google_search_tool,
    safety_settings,
    create_generate_config,
    tracked_channels,
    max_history,
)


# --- API Key Rotation Manager ---
class APIKeyManager:
    """Manages API key rotation for handling 429 rate limit errors."""
    
    def __init__(self, api_keys):
        self.api_keys = api_keys if api_keys else []
        self.current_index = 0
        self._client = None
        
        if self.api_keys:
            self._client = genai.Client(api_key=self.api_keys[0])
            print(f"🔑 API Key Manager initialized with {len(self.api_keys)} key(s). Using key 1.")
        else:
            print("⚠️ Warning: No API keys found!")
    
    @property
    def client(self):
        """Get the current Gemini client."""
        return self._client
    
    def rotate_key(self):
        """Rotate to the next API key. Returns True if successfully rotated."""
        if len(self.api_keys) <= 1:
            print("⚠️ Only one API key available, cannot rotate.")
            return False
        
        # Move to next key (wrap around to 1 if at end)
        self.current_index = (self.current_index + 1) % len(self.api_keys)
        new_key = self.api_keys[self.current_index]
        self._client = genai.Client(api_key=new_key)
        
        print(f"🔄 Rotated to API key {self.current_index + 1} of {len(self.api_keys)}")
        return True
    
    def get_current_key_info(self):
        """Get info about the current key (for logging, not the actual key)."""
        return f"Key {self.current_index + 1} of {len(self.api_keys)}"


# --- Initialize API Key Manager ---
api_key_manager = APIKeyManager(gemini_api_keys)

# For backwards compatibility
client = api_key_manager.client


def is_rate_limit_error(error):
    """Check if an exception is a 429 rate limit error."""
    error_str = str(error)
    return "429" in error_str and ("RESOURCE_EXHAUSTED" in error_str or "rate" in error_str.lower() or "quota" in error_str.lower())


def is_free_tier_error(error):
    """Check if a 429 error is specifically a free-tier limitation (not a normal rate limit).
    
    Free tier errors for paid-only models/features typically contain keywords like
    'free tier', 'billing', 'paid', or mention the specific model isn't available.
    """
    error_str = str(error).lower()
    if "429" not in str(error):
        return False
    free_tier_indicators = [
        "free tier",
        "free of charge",
        "billing",
        "paid tier",
        "paid api",
        "enable billing",
        "upgrade",
        "not available for",
        "not supported for",
    ]
    return any(indicator in error_str for indicator in free_tier_indicators)


async def execute_with_retry(func, *args, **kwargs):
    """Execute a function with automatic API key rotation on 429 errors.
    
    Args:
        func: The function to execute (should be a lambda or partial that uses api_key_manager.client)
        *args, **kwargs: Arguments to pass to the function
    
    Returns:
        The result of the function call
    
    Raises:
        Exception: If all API keys are exhausted or a non-429 error occurs
    """
    # Track how many keys we've tried
    keys_tried = 0
    total_keys = len(api_key_manager.api_keys)
    last_error = None
    
    while keys_tried < total_keys:
        try:
            # Execute the function
            result = await asyncio.to_thread(func)
            return result
        except Exception as e:
            if is_rate_limit_error(e):
                last_error = e
                keys_tried += 1
                print(f"⚠️ Rate limit hit on {api_key_manager.get_current_key_info()}: {str(e)[:100]}...")
                
                if keys_tried < total_keys:
                    # Try to rotate to the next key
                    if api_key_manager.rotate_key():
                        print(f"🔄 Retrying with {api_key_manager.get_current_key_info()}...")
                        continue
                
                # All keys exhausted
                print(f"❌ All {total_keys} API key(s) exhausted due to rate limits.")
                raise Exception(f"All {total_keys} API key(s) have been rate limited. Please wait and try again later. Last error: {str(e)}")
            else:
                # Non-rate-limit error, re-raise immediately
                raise e
    
    # Should not reach here, but just in case
    if last_error:
        raise last_error

# --- Shared State ---
message_history = {}
tracked_threads = []

# Context-scoped settings (keyed like message_history)
# Keys: ("thread", thread_id), ("dm", user_id), ("tracked", user_id), ("mention", user_id)
context_settings = {}

# Legacy: removed deprecated user_settings and thread_settings
# All settings now use context_settings exclusively

# Default settings
default_settings = {
    "thinking_level": "minimal",  # minimal, low, medium, high
    "persona": None  # Custom persona, None means use default system instruction
}

# Pending context cache (for /context command)
# Keys: user_id → {
#     "contents": list of Content objects,
#     "remaining_uses": int (messages left before context clears),
#     "listen_channel_id": int or None (channel to auto-respond without @mention)
# }
# This persists for remaining_uses messages, then clears.
pending_context = {}


def set_pending_context(context_key, contents, remaining_uses=1, listen_channel_id=None):
    """Store pending context for a specific context (used by /context command).
    
    Args:
        context_key: Tuple like ("dm", user_id) or ("tracked", user_id) etc.
        contents: List of Content objects to use as context
        remaining_uses: Number of messages the context should persist for
        listen_channel_id: Optional channel ID where bot should auto-respond without @mention
    """
    pending_context[context_key] = {
        "contents": contents,
        "remaining_uses": remaining_uses,
        "listen_channel_id": listen_channel_id,
    }



def get_pending_context(context_key):
    """Retrieve pending context for a specific context without clearing it.
    
    Args:
        context_key: Tuple like ("dm", user_id) or ("tracked", user_id) etc.
    
    Returns:
        List of Content objects, or empty list if no pending context.
    """
    ctx = pending_context.get(context_key)
    if ctx:
        return ctx["contents"]
    return []


def decrement_pending_context(context_key):
    """Decrement the remaining uses for a context's pending context.
    
    Call this after using context in a message. Clears context when uses reach 0.
    
    Args:
        context_key: Tuple like ("dm", user_id) or ("tracked", user_id) etc.
    
    Returns:
        Remaining uses after decrement, or 0 if no context.
    """
    ctx = pending_context.get(context_key)
    if ctx:
        ctx["remaining_uses"] -= 1
        if ctx["remaining_uses"] <= 0:
            del pending_context[context_key]
            return 0
        return ctx["remaining_uses"]
    return 0


def get_and_clear_pending_context(context_key):
    """Retrieve and clear pending context for a context (legacy, clears immediately).
    
    Args:
        context_key: Tuple like ("dm", user_id) or ("tracked", user_id) etc.
    
    Returns:
        List of Content objects, or empty list if no pending context.
    """
    ctx = pending_context.pop(context_key, None)
    if ctx:
        return ctx["contents"]
    return []


def has_pending_context(context_key):
    """Check if a context has pending context.
    
    Args:
        context_key: Tuple like ("dm", user_id) or ("tracked", user_id) etc.
    
    Returns:
        True if context has pending context, False otherwise.
    """
    return context_key in pending_context


def get_pending_context_remaining(context_key):
    """Get remaining uses for pending context without decrementing.
    
    Args:
        context_key: Tuple like (\"dm\", user_id) or (\"tracked\", user_id) etc.
    
    Returns:
        Number of remaining uses, or 0 if no pending context.
    """
    ctx = pending_context.get(context_key)
    if ctx:
        return ctx.get("remaining_uses", 0)
    return 0


def get_pending_context_channel(context_key):
    """Get the channel ID where bot should auto-respond for this context.
    
    Args:
        context_key: Tuple like ("dm", user_id) or ("tracked", user_id) etc.
    
    Returns:
        Channel ID or None if no auto-respond channel set.
    """
    ctx = pending_context.get(context_key)
    if ctx:
        return ctx.get("listen_channel_id")
    return None


def get_pending_context_remaining(context_key):
    """Get remaining uses for a context's pending context.
    
    Args:
        context_key: Tuple like ("dm", user_id) or ("tracked", user_id) etc.
    
    Returns:
        Remaining uses, or 0 if no context.
    """
    ctx = pending_context.get(context_key)
    if ctx:
        return ctx["remaining_uses"]
    return 0


def has_auto_respond_for_channel(user_id, channel_id):
    """Check if user has pending context set to auto-respond in this channel.
    
    This is used by the router to determine if bot should respond without @mention.
    
    Args:
        user_id: Discord user ID
        channel_id: Channel ID to check
    
    Returns:
        True if any of user's pending contexts has this channel as listen_channel_id.
    """
    for ctx_key, ctx_data in pending_context.items():
        # Check if this context belongs to this user
        if len(ctx_key) >= 2 and ctx_key[1] == user_id:
            if ctx_data.get("listen_channel_id") == channel_id:
                return True
    return False



# --- Settings Management ---

def get_settings_key(message):
    """Get the appropriate settings key for the current context.
    
    Returns:
        A tuple key for context_settings dict.
        - Thread: ("thread", thread_id)
        - DM: ("dm", user_id)
        - Tracked channel: ("tracked", user_id)
        - @mention elsewhere: ("mention", user_id)
    """
    import discord
    
    # Thread: use thread_id (shared settings for all users in thread)
    if message.channel.id in tracked_threads:
        return ("thread", message.channel.id)
    
    # DM: use user_id with dm prefix
    if isinstance(message.channel, discord.DMChannel):
        return ("dm", message.author.id)
    
    # Tracked channel: use user_id with tracked prefix
    if message.channel.id in tracked_channels:
        return ("tracked", message.author.id)
    
    # @mention elsewhere: use user_id with mention prefix
    return ("mention", message.author.id)


def get_settings(message):
    """Get settings for the current context.
    
    Scoping (separate settings for each):
    - Thread: Shared by all users in that thread
    - DM: User's personal DM settings
    - Tracked channel: User's personal tracked channel settings
    - @mention elsewhere: User's personal @mention settings
    """
    settings_key = get_settings_key(message)
    return context_settings.get(settings_key, default_settings.copy())


def set_settings_for_context(settings_key, settings):
    """Set settings for a specific context key."""
    context_settings[settings_key] = settings


def set_settings(context_id, is_thread, settings):
    """Set settings for a user or thread (legacy, for backwards compatibility)."""
    if is_thread:
        context_settings[("thread", context_id)] = settings
    else:
        pass


def get_effective_system_instruction(settings, user_display_name=None, user_username=None):
    """Get the system instruction with persona applied if set.
    
    Args:
        settings: User/thread settings dict
        user_display_name: Display name of the user (optional)
        user_username: Username of the user without @ (optional)
    """
    base_instruction = get_system_instruction(user_display_name, user_username)
    if settings.get("persona"):
        return f"{settings['persona']}\n\n{base_instruction}"
    return base_instruction


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
        file_info = await asyncio.to_thread(api_key_manager.client.files.get, name=uploaded_file.name)
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
# History is scoped by context to prevent persona leakage:
# - Threads: keyed by thread_id (shared by all users in thread)
# - DMs: keyed by user_id
# - Tracked channels: keyed by user_id
# - @mentions elsewhere: global per-user history (shared across all non-tracked channels)

def get_history_key(message):
    """Get the appropriate history key for the current context.
    
    Returns:
        A tuple key for message_history dict.
        - Thread: ("thread", thread_id)
        - DM: ("dm", user_id)
        - Tracked channel: ("tracked", user_id)
        - @mention elsewhere: ("mention", user_id) - global per-user
    """
    import discord
    
    # Thread: use thread_id (shared history for all users in thread)
    if message.channel.id in tracked_threads:
        return ("thread", message.channel.id)
    
    # DM: use user_id
    if isinstance(message.channel, discord.DMChannel):
        return ("dm", message.author.id)
    
    # Tracked channel: use user_id
    if message.channel.id in tracked_channels:
        return ("tracked", message.author.id)
    
    # @mention elsewhere: global per-user history (shared across all non-tracked channels)
    return ("mention", message.author.id)


def update_message_history(message, content):
    """Update message history with a Content object.
    
    Args:
        message: The Discord message object (used to determine context)
        content: A Content object (with role and parts)
    """
    if content is None:
        return
    
    history_key = get_history_key(message)
    
    if history_key in message_history:
        message_history[history_key].append(content)
        if len(message_history[history_key]) > max_history:
            message_history[history_key].pop(0)
    else:
        message_history[history_key] = [content]


def get_message_history_contents(message):
    """Get message history as a list of Content objects for Gemini API.
    
    Args:
        message: The Discord message object (used to determine context)
    
    Returns:
        List of Content objects, or empty list if no history.
    """
    history_key = get_history_key(message)
    return message_history.get(history_key, [])


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

async def generate_response_with_text(contents, settings, user_display_name=None, user_username=None):
    """Generate a response for text input with optional history.
    
    Args:
        contents: Either a string (single message) or list of Content objects (with history)
        settings: User/thread settings dict
        user_display_name: Display name of the user (optional)
        user_username: Username of the user without @ (optional)
    
    Returns:
        Response text string
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings, user_display_name, user_username)
        thinking_level = settings.get("thinking_level", "minimal")
        
        config = create_generate_config(
            system_instruction=effective_system_instruction,
            thinking_level=thinking_level,
            tools=[google_search_tool] if google_search_tool else None,
        )
        
        # Use execute_with_retry for automatic key rotation on 429 errors
        response = await execute_with_retry(
            lambda: api_key_manager.client.models.generate_content(
                model=gemini_model,
                contents=contents,
                config=config
            )
        )
        # Handle case where response.text is None
        if response.text is None:
            return "❌ I received an empty response. Please try again."
        return convert_latex_to_discord(response.text)
    except Exception as e:
        return "❌ Exception: " + str(e)


async def process_image_attachment(attachment, user_text, settings, history=None, user_display_name=None, user_username=None):
    """Process an image attachment using the Files API with optional history.
    
    Args:
        attachment: Discord attachment object
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
        user_display_name: Display name of the user (optional)
        user_username: Username of the user without @ (optional)
    
    Returns:
        Tuple of (response_text, history_parts, uploaded_file) for history tracking.
        Note: history_parts contains text-only description (no file URI) to avoid
        403 errors when files expire on Gemini's side.
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings, user_display_name, user_username)
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
            # Upload file to Gemini with retry on 429 errors
            uploaded_file = await execute_with_retry(
                lambda: api_key_manager.client.files.upload(file=tmp_path)
            )
            
            prompt = user_text if user_text else default_image_prompt
            
            # Build user content parts for this message (with actual file for current request)
            user_parts = [
                Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
                Part(text=prompt)
            ]
            
            # Build contents: history + current message
            if history:
                contents = history + [Content(role="user", parts=user_parts)]
            else:
                contents = [Content(role="user", parts=user_parts)]
            
            config = create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
            )
            
            # Use execute_with_retry for automatic key rotation on 429 errors
            response = await execute_with_retry(
                lambda: api_key_manager.client.models.generate_content(
                    model=gemini_model,
                    contents=contents,
                    config=config
                )
            )
            
            # Create sanitized parts for history (text-only, no file URI that could expire)
            history_parts = [
                Part(text=f"[Image: {attachment.filename}]\n{prompt}")
            ]
            
            # Handle case where response.text is None
            response_text = response.text if response.text else "❌ I received an empty response. Please try again."
            return (convert_latex_to_discord(response_text), history_parts, uploaded_file)
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return ("❌ Exception: " + str(e), None, None)


async def process_image_attachments(attachments, user_text, settings, history=None, user_display_name=None, user_username=None):
    """Process multiple image attachments using the Files API.
    
    Args:
        attachments: List of Discord attachment objects
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
        user_display_name: Display name of the user (optional)
        user_username: Username of the user without @ (optional)
    
    Returns:
        Tuple of (response_text, history_parts, uploaded_files) for history tracking.
    """
    # Handle single attachment case
    if len(attachments) == 1:
        response, parts, file = await process_image_attachment(
            attachments[0], user_text, settings, history, user_display_name, user_username
        )
        return (response, parts, [file] if file else None)
    
    try:
        effective_system_instruction = get_effective_system_instruction(settings, user_display_name, user_username)
        thinking_level = settings.get("thinking_level", "minimal")
        
        uploaded_files = []
        temp_paths = []
        filenames = []
        
        # Download and upload all images
        async with aiohttp.ClientSession() as session:
            for attachment in attachments:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200:
                        continue
                    image_data = await resp.read()
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.filename)[1]) as tmp_file:
                    tmp_file.write(image_data)
                    temp_paths.append(tmp_file.name)
                
                uploaded_file = await execute_with_retry(
                    lambda path=temp_paths[-1]: api_key_manager.client.files.upload(file=path)
                )
                uploaded_files.append(uploaded_file)
                filenames.append(attachment.filename)
        
        if not uploaded_files:
            return ("❌ Unable to download any of the images.", None, None)
        
        try:
            prompt = user_text if user_text else default_image_prompt
            
            # Build user content parts with all images
            user_parts = []
            for uploaded_file in uploaded_files:
                user_parts.append(Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type))
            user_parts.append(Part(text=prompt))
            
            if history:
                contents = history + [Content(role="user", parts=user_parts)]
            else:
                contents = user_parts
            
            config = create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
            )
            
            response = await execute_with_retry(
                lambda: api_key_manager.client.models.generate_content(
                    model=gemini_model,
                    contents=contents,
                    config=config
                )
            )
            
            history_parts = [Part(text=f"[Images: {', '.join(filenames)}]\n{prompt}")]
            # Handle case where response.text is None
            response_text = response.text if response.text else "❌ I received an empty response. Please try again."
            return (convert_latex_to_discord(response_text), history_parts, uploaded_files)
        finally:
            for tmp_path in temp_paths:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                
    except Exception as e:
        return ("❌ Exception: " + str(e), None, None)


async def process_video_attachment(attachment, user_text, settings, history=None, user_display_name=None, user_username=None):

    """Process a video attachment using the Files API with proper state waiting.
    
    Args:
        attachment: Discord attachment object
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
        user_display_name: Display name of the user (optional)
        user_username: Username of the user without @ (optional)
    
    Returns:
        Tuple of (response_text, history_parts, uploaded_file) for history tracking.
        Note: history_parts contains text-only description (no file URI) to avoid
        403 errors when files expire on Gemini's side.
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings, user_display_name, user_username)
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
            # Upload file to Gemini with retry on 429 errors
            uploaded_file = await execute_with_retry(
                lambda: api_key_manager.client.files.upload(file=tmp_path)
            )
            
            # Wait for video file to become ACTIVE (videos need processing time)
            print(f"Waiting for video file to become active: {uploaded_file.name}")
            active_file = await wait_for_file_active(uploaded_file)
            print(f"Video file is now active: {active_file.name}")
            
            prompt = user_text if user_text else "What is this video about? Summarize it for me."
            
            # Build user content parts for this message (with actual file for current request)
            user_parts = [
                Part.from_uri(file_uri=active_file.uri, mime_type=active_file.mime_type),
                Part(text=prompt)
            ]
            
            # Build contents: history + current message
            if history:
                contents = history + [Content(role="user", parts=user_parts)]
            else:
                contents = [Content(role="user", parts=user_parts)]
            
            config = create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
            )
            
            # Use execute_with_retry for automatic key rotation on 429 errors
            response = await execute_with_retry(
                lambda: api_key_manager.client.models.generate_content(
                    model=gemini_model,
                    contents=contents,
                    config=config
                )
            )
            
            # Create sanitized parts for history (text-only, no file URI that could expire)
            history_parts = [
                Part(text=f"[Video: {attachment.filename}]\n{prompt}")
            ]
            
            # Handle case where response.text is None
            response_text = response.text if response.text else "❌ I received an empty response. Please try again."
            return (convert_latex_to_discord(response_text), history_parts, active_file)
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return ("❌ Exception: " + str(e), None, None)


async def process_video_attachments(attachments, user_text, settings, history=None, user_display_name=None, user_username=None):
    """Process multiple video attachments using the Files API.
    
    Args:
        attachments: List of Discord attachment objects
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
        user_display_name: Display name of the user (optional)
        user_username: Username of the user without @ (optional)
    
    Returns:
        Tuple of (response_text, history_parts, uploaded_files) for history tracking.
    """
    # Handle single attachment case
    if len(attachments) == 1:
        response, parts, file = await process_video_attachment(
            attachments[0], user_text, settings, history, user_display_name, user_username
        )
        return (response, parts, [file] if file else None)
    
    try:
        effective_system_instruction = get_effective_system_instruction(settings, user_display_name, user_username)
        thinking_level = settings.get("thinking_level", "minimal")
        
        uploaded_files = []
        temp_paths = []
        filenames = []
        
        # Download and upload all videos
        async with aiohttp.ClientSession() as session:
            for attachment in attachments:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200:
                        continue
                    video_data = await resp.read()
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.filename)[1]) as tmp_file:
                    tmp_file.write(video_data)
                    temp_paths.append(tmp_file.name)
                
                uploaded_file = await execute_with_retry(
                    lambda path=temp_paths[-1]: api_key_manager.client.files.upload(file=path)
                )
                
                # Wait for video to become active
                print(f"Waiting for video file to become active: {uploaded_file.name}")
                active_file = await wait_for_file_active(uploaded_file)
                print(f"Video file is now active: {active_file.name}")
                
                uploaded_files.append(active_file)
                filenames.append(attachment.filename)
        
        if not uploaded_files:
            return ("❌ Unable to download any of the videos.", None, None)
        
        try:
            prompt = user_text if user_text else "What are these videos about? Summarize them for me."
            
            # Build user content parts with all videos
            user_parts = []
            for uploaded_file in uploaded_files:
                user_parts.append(Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type))
            user_parts.append(Part(text=prompt))
            
            if history:
                contents = history + [Content(role="user", parts=user_parts)]
            else:
                contents = user_parts
            
            config = create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
            )
            
            response = await execute_with_retry(
                lambda: api_key_manager.client.models.generate_content(
                    model=gemini_model,
                    contents=contents,
                    config=config
                )
            )
            
            history_parts = [Part(text=f"[Videos: {', '.join(filenames)}]\n{prompt}")]
            # Handle case where response.text is None
            response_text = response.text if response.text else "❌ I received an empty response. Please try again."
            return (convert_latex_to_discord(response_text), history_parts, uploaded_files)
        finally:
            for tmp_path in temp_paths:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                
    except Exception as e:
        return ("❌ Exception: " + str(e), None, None)


async def process_file_attachment(attachment, user_text, settings, history=None, user_display_name=None, user_username=None):

    """Process PDF or text file attachments using the Files API.
    
    Args:
        attachment: Discord attachment object
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
        user_display_name: Display name of the user (optional)
        user_username: Username of the user without @ (optional)
    
    Returns:
        Tuple of (response_text, history_parts, uploaded_file) for history tracking.
        Note: history_parts contains text-only description (no file URI) to avoid
        403 errors when files expire on Gemini's side.
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings, user_display_name, user_username)
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
            # Upload file to Gemini with retry on 429 errors
            uploaded_file = await execute_with_retry(
                lambda: api_key_manager.client.files.upload(file=tmp_path)
            )
            
            prompt = user_text if user_text else default_pdf_and_txt_prompt
            
            # Build user content parts for this message (with actual file for current request)
            user_parts = [
                Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
                Part(text=prompt)
            ]
            
            # Build contents: history + current message
            if history:
                contents = history + [Content(role="user", parts=user_parts)]
            else:
                contents = user_parts
            
            config = create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
            )
            
            # Use execute_with_retry for automatic key rotation on 429 errors
            response = await execute_with_retry(
                lambda: api_key_manager.client.models.generate_content(
                    model=gemini_model,
                    contents=contents,
                    config=config
                )
            )
            
            # Create sanitized parts for history (text-only, no file URI that could expire)
            history_parts = [
                Part(text=f"[File: {attachment.filename}]\n{prompt}")
            ]
            
            # Handle case where response.text is None
            response_text = response.text if response.text else "❌ I received an empty response. Please try again."
            return (convert_latex_to_discord(response_text), history_parts, uploaded_file)
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return ("❌ Exception: " + str(e), None, None)


async def process_file_attachments(attachments, user_text, settings, history=None, user_display_name=None, user_username=None):
    """Process multiple file attachments using the Files API.
    
    Args:
        attachments: List of Discord attachment objects
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
        user_display_name: Display name of the user (optional)
        user_username: Username of the user without @ (optional)
    
    Returns:
        Tuple of (response_text, history_parts, uploaded_files) for history tracking.
    """
    # Handle single attachment case
    if len(attachments) == 1:
        response, parts, file = await process_file_attachment(
            attachments[0], user_text, settings, history, user_display_name, user_username
        )
        return (response, parts, [file] if file else None)
    
    try:
        effective_system_instruction = get_effective_system_instruction(settings, user_display_name, user_username)
        thinking_level = settings.get("thinking_level", "minimal")
        
        uploaded_files = []
        temp_paths = []
        filenames = []
        
        # Download and upload all files
        async with aiohttp.ClientSession() as session:
            for attachment in attachments:
                async with session.get(attachment.url) as resp:
                    if resp.status != 200:
                        continue
                    file_data = await resp.read()
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.filename)[1]) as tmp_file:
                    tmp_file.write(file_data)
                    temp_paths.append(tmp_file.name)
                
                uploaded_file = await execute_with_retry(
                    lambda path=temp_paths[-1]: api_key_manager.client.files.upload(file=path)
                )
                uploaded_files.append(uploaded_file)
                filenames.append(attachment.filename)
        
        if not uploaded_files:
            return ("❌ Unable to download any of the files.", None, None)
        
        try:
            prompt = user_text if user_text else default_pdf_and_txt_prompt
            
            # Build user content parts with all files
            user_parts = []
            for uploaded_file in uploaded_files:
                user_parts.append(Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type))
            user_parts.append(Part(text=prompt))
            
            if history:
                contents = history + [Content(role="user", parts=user_parts)]
            else:
                contents = user_parts
            
            config = create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
            )
            
            response = await execute_with_retry(
                lambda: api_key_manager.client.models.generate_content(
                    model=gemini_model,
                    contents=contents,
                    config=config
                )
            )
            
            history_parts = [Part(text=f"[Files: {', '.join(filenames)}]\n{prompt}")]
            # Handle case where response.text is None
            response_text = response.text if response.text else "❌ I received an empty response. Please try again."
            return (convert_latex_to_discord(response_text), history_parts, uploaded_files)
        finally:
            for tmp_path in temp_paths:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                
    except Exception as e:
        return ("❌ Exception: " + str(e), None, None)


async def process_youtube_url(url, user_text, settings, history=None, user_display_name=None, user_username=None):

    """Process YouTube video URL using FileData.
    
    Args:
        url: YouTube URL
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
        user_display_name: Display name of the user (optional)
        user_username: Username of the user without @ (optional)
    
    Returns:
        Tuple of (response_text, user_content_parts) for history tracking
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings, user_display_name, user_username)
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
            contents = [Content(role="user", parts=user_parts)]
        
        config = create_generate_config(
            system_instruction=effective_system_instruction,
            thinking_level=thinking_level,
        )
        
        # Use execute_with_retry for automatic key rotation on 429 errors
        response = await execute_with_retry(
            lambda: api_key_manager.client.models.generate_content(
                model=gemini_model,
                contents=contents,
                config=config
            )
        )
        # Handle case where response.text is None
        response_text = response.text if response.text else "❌ I received an empty response. Please try again."
        return (convert_latex_to_discord(response_text), user_parts)
    except Exception as e:
        return ("❌ Exception: " + str(e), None)


async def process_website_url(url, user_text, settings, history=None, user_display_name=None, user_username=None):
    """Process website URL using URL context tool.
    
    Args:
        url: Website URL
        user_text: User's message text
        settings: User/thread settings dict
        history: Optional list of Content objects (message history)
        user_display_name: Display name of the user (optional)
        user_username: Username of the user without @ (optional)
    
    Returns:
        Tuple of (response_text, user_content_parts) for history tracking
    """
    try:
        effective_system_instruction = get_effective_system_instruction(settings, user_display_name, user_username)
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
            contents = [Content(role="user", parts=user_parts)]
        
        config = create_generate_config(
            system_instruction=effective_system_instruction,
            thinking_level=thinking_level,
            tools=[url_context_tool],
        )
        
        # Use execute_with_retry for automatic key rotation on 429 errors
        response = await execute_with_retry(
            lambda: api_key_manager.client.models.generate_content(
                model=gemini_model,
                contents=contents,
                config=config
            )
        )
        # Handle case where response.text is None
        response_text = response.text if response.text else "❌ I received an empty response. Please try again."
        return (convert_latex_to_discord(response_text), user_parts)
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
        
        # Track keys tried manually for image generation (to detect free-tier errors)
        keys_tried = 0
        total_keys = len(api_key_manager.api_keys)
        last_error = None
        
        while keys_tried < total_keys:
            try:
                response = await asyncio.to_thread(
                    lambda: api_key_manager.client.models.generate_content(
                        model=image_model,
                        contents=contents,
                        config=config
                    )
                )
                break  # Success
            except Exception as e:
                if is_free_tier_error(e):
                    # This key is free-tier, try next key
                    keys_tried += 1
                    last_error = e
                    if keys_tried < total_keys and api_key_manager.rotate_key():
                        continue
                    # All keys are free-tier
                    return ("❌ Image generation requires a **paid Gemini API key**. All your configured API keys appear to be free-tier keys.\n\n"
                            "💡 To use `/image`, upgrade at least one of your API keys to a paid tier at [Google AI Studio](https://aistudio.google.com/).", None, None)
                elif is_rate_limit_error(e):
                    # Normal rate limit, try next key
                    keys_tried += 1
                    last_error = e
                    if keys_tried < total_keys and api_key_manager.rotate_key():
                        continue
                    raise Exception(f"All {total_keys} API key(s) have been rate limited. Please wait and try again later.")
                else:
                    raise e
        
        # Extract text and image from response
        text_response = None
        image_bytes = None
        image_mime_type = None
        
        for part in response.parts:
            if part.text is not None:
                text_response = convert_latex_to_discord(part.text)
            elif part.inline_data is not None:
                image_bytes = part.inline_data.data
                image_mime_type = part.inline_data.mime_type
        
        return (text_response, image_bytes, image_mime_type)
        
    except Exception as e:
        return (f"❌ Exception: {str(e)}", None, None)
