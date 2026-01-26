import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import re
import asyncio
import tempfile
import os

# Google GenAI imports
from google import genai
from google.genai import types
from google.genai.types import Part, Content

from config import *

GEMINI_API_KEY = gemini_api_key
DISCORD_BOT_TOKEN = discord_bot_token
MAX_HISTORY = max_history

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


async def wait_for_file_active(uploaded_file, max_wait_seconds=120, poll_interval=2):
    """Wait for a file to become ACTIVE after upload.
    
    Video files often need processing time before they can be used.
    Returns the file when active, or raises an exception on timeout.
    """
    import time
    start_time = time.time()
    
    while True:
        # Check if file is active
        file_info = client.files.get(name=uploaded_file.name)
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

def get_settings(message):
    # Get settings for the current context (user or thread).
    if message.channel.id in tracked_threads:
        return thread_settings.get(message.channel.id, default_settings.copy())
    else:
        return user_settings.get(message.author.id, default_settings.copy())

def set_settings(context_id, is_thread, settings):
    # Set settings for a user or thread.
    if is_thread:
        thread_settings[context_id] = settings
    else:
        user_settings[context_id] = settings

def get_effective_system_instruction(settings):
    # Get the system instruction with persona applied if set.
    if settings.get("persona"):
        return f"{settings['persona']}\n\n{system_instruction}"
    return system_instruction

# Keep bot running 24/7
from keep_alive import keep_alive
keep_alive()

# --- Gemini Client Setup ---
client = genai.Client(api_key=GEMINI_API_KEY)

# --- Discord Code ---

# Initialize Discord bot
defaultIntents = discord.Intents.all()
defaultIntents.message_content = True
bot = commands.Bot(
    command_prefix="!",
    intents=defaultIntents,
    help_command=None,
    activity=discord.Activity(
        type=discord.ActivityType.custom,
        name="The best Discord chatbot!"
    )
)

@bot.event
async def on_ready():
    print(f'Techiee logged in as {bot.user}')

@bot.event
async def on_message(message):
    asyncio.create_task(process_message(message))

async def process_message(message):
    # Ignore messages sent by the bot or if mention everyone is used
    if message.author == bot.user or message.mention_everyone:
        return
    
    # Ignore other bots
    if message.author.bot:
        return

    # Check if the message is a DM or in tracked channels/threads
    if isinstance(message.channel, discord.DMChannel) or message.channel.id in tracked_channels or message.channel.id in tracked_threads:
        cleaned_text = clean_discord_message(message.content)
        
        # Get settings for this context
        settings = get_settings(message)
        
        # Use Discord's built-in typing context manager - it handles the 10s refresh automatically
        async with message.channel.typing():
            # Check for image attachments
            if message.attachments:
                for attachment in message.attachments:
                    print(f"New Attachment Message FROM: {message.author.name} : {cleaned_text}")
                    
                    # Image processing
                    if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                        print("Processing Image")
                        response_text = await process_image_attachment(attachment, cleaned_text, settings)
                        await split_and_send_messages(message, response_text, 1900)
                        return
                    
                    # Video processing
                    elif any(attachment.filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.mpeg', '.mpg', '.wmv', '.flv', '.3gp']):
                        print("Processing Video")
                        response_text = await process_video_attachment(attachment, cleaned_text, settings)
                        await split_and_send_messages(message, response_text, 1900)
                        return
                    
                    # PDF and text file processing
                    elif attachment.filename.lower().endswith('.pdf') or attachment.filename.lower().endswith('.txt'):
                        print(f"Processing {'PDF' if attachment.filename.lower().endswith('.pdf') else 'Text'} File")
                        response_text = await process_file_attachment(attachment, cleaned_text, settings)
                        await split_and_send_messages(message, response_text, 1900)
                        return
                    
                    else:
                        # Try to process as generic text file
                        print("Processing as generic attachment")
                        response_text = await process_file_attachment(attachment, cleaned_text, settings)
                        await split_and_send_messages(message, response_text, 1900)
                        return
            
            # Text-only message processing
            else:
                print(f"New Text Message FROM: {message.author.name} : {cleaned_text}")
                
                # Check for URLs
                url = extract_url(cleaned_text)
                if url is not None:
                    print(f"Got URL: {url}")
                    if is_youtube_url(url):
                        print("Processing YouTube Video")
                        response_text = await process_youtube_url(url, cleaned_text, settings)
                    else:
                        print("Processing Website URL")
                        response_text = await process_website_url(url, cleaned_text, settings)
                    await split_and_send_messages(message, response_text, 1900)
                    return
                
                # Regular text conversation with history
                if MAX_HISTORY == 0:
                    response_text = await generate_response_with_text(cleaned_text, settings)
                    await split_and_send_messages(message, response_text, 1900)
                    return
                
                # Add user's question to history
                update_message_history(message.author.id, cleaned_text)
                response_text = await generate_response_with_text(get_formatted_message_history(message.author.id), settings)
                # Add AI response to history
                update_message_history(message.author.id, response_text)
                await split_and_send_messages(message, response_text, 1900)


# --- Response Generation Functions ---

async def generate_response_with_text(message_text, settings):
    # Generate a response for text-only input (with Google Search grounding).
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        # Include google_search_tool if you have billing setup - model automatically decides when to search
        response = client.models.generate_content(
            model=gemini_model,
            contents=message_text,
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


async def process_image_attachment(attachment, user_text, settings):
    # Process an image attachment using the Files API.
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status != 200:
                    return "❌ Unable to download the image."
                image_data = await resp.read()
        
        # Create a temporary file and upload to Gemini
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.filename)[1]) as tmp_file:
            tmp_file.write(image_data)
            tmp_path = tmp_file.name
        
        try:
            # Upload file to Gemini
            uploaded_file = client.files.upload(file=tmp_path)
            
            prompt = user_text if user_text else default_image_prompt
            
            response = client.models.generate_content(
                model=gemini_model,
                contents=[
                    Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
                    prompt
                ],
                config=create_generate_config(
                    system_instruction=effective_system_instruction,
                    thinking_level=thinking_level,
                )
            )
            return response.text
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return "❌ Exception: " + str(e)


async def process_video_attachment(attachment, user_text, settings):
    """Process a video attachment using the Files API with proper state waiting."""
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        # Download the video
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status != 200:
                    return "❌ Unable to download the video."
                video_data = await resp.read()
        
        # Create a temporary file and upload to Gemini
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.filename)[1]) as tmp_file:
            tmp_file.write(video_data)
            tmp_path = tmp_file.name
        
        try:
            # Upload file to Gemini
            uploaded_file = client.files.upload(file=tmp_path)
            
            # Wait for video file to become ACTIVE (videos need processing time)
            print(f"Waiting for video file to become active: {uploaded_file.name}")
            active_file = await wait_for_file_active(uploaded_file)
            print(f"Video file is now active: {active_file.name}")
            
            prompt = user_text if user_text else "What is this video about? Summarize it for me."
            
            response = client.models.generate_content(
                model=gemini_model,
                contents=[
                    Part.from_uri(file_uri=active_file.uri, mime_type=active_file.mime_type),
                    prompt
                ],
                config=create_generate_config(
                    system_instruction=effective_system_instruction,
                    thinking_level=thinking_level,
                )
            )
            return response.text
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return "❌ Exception: " + str(e)


async def process_file_attachment(attachment, user_text, settings):
    #Process PDF or text file attachments using the Files API.
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        # Download the file
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status != 200:
                    return "❌ Unable to download the attachment."
                file_data = await resp.read()
        
        # Create a temporary file and upload to Gemini
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.filename)[1]) as tmp_file:
            tmp_file.write(file_data)
            tmp_path = tmp_file.name
        
        try:
            # Upload file to Gemini
            uploaded_file = client.files.upload(file=tmp_path)
            
            prompt = user_text if user_text else default_pdf_and_txt_prompt
            
            response = client.models.generate_content(
                model=gemini_model,
                contents=[
                    Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
                    prompt
                ],
                config=create_generate_config(
                    system_instruction=effective_system_instruction,
                    thinking_level=thinking_level,
                )
            )
            return response.text
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return "❌ Exception: " + str(e)


async def process_youtube_url(url, user_text, settings):
    # Process YouTube video URL using FileData.
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        prompt = user_text.replace(url, "").strip() if user_text else default_url_prompt
        
        response = client.models.generate_content(
            model=gemini_model,
            contents=Content(
                parts=[
                    Part(file_data=types.FileData(file_uri=url)),
                    Part(text=prompt)
                ]
            ),
            config=create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
            )
        )
        return response.text
    except Exception as e:
        return "❌ Exception: " + str(e)


async def process_website_url(url, user_text, settings):
    # Process website URL using URL context tool.
    try:
        effective_system_instruction = get_effective_system_instruction(settings)
        thinking_level = settings.get("thinking_level", "minimal")
        
        prompt = user_text if user_text else f"{default_url_prompt} {url}"
        
        # If user provided custom text, make sure the URL is included
        if user_text and url not in user_text:
            prompt = f"{user_text} {url}"
        
        response = client.models.generate_content(
            model=gemini_model,
            contents=prompt,
            config=create_generate_config(
                system_instruction=effective_system_instruction,
                thinking_level=thinking_level,
                tools=[url_context_tool],
            )
        )
        return response.text
    except Exception as e:
        return "❌ Exception: " + str(e)


# --- Message History ---

def update_message_history(user_id, text):
    # Update message history for a user.
    # Skip None values to prevent join errors later
    if text is None:
        return
    if user_id in message_history:
        message_history[user_id].append(text)
        if len(message_history[user_id]) > MAX_HISTORY:
            message_history[user_id].pop(0)
    else:
        message_history[user_id] = [text]

def get_formatted_message_history(user_id):
    # Get formatted message history for a user.
    if user_id in message_history:
        return '\n\n'.join(message_history[user_id])
    else:
        return "No messages found for this user."


# --- Utility Functions ---

async def split_and_send_messages(message, text, max_length):
    # Split long messages and send them sequentially, using reply for first message.
    messages = []
    for i in range(0, len(text), max_length):
        sub_message = text[i:i+max_length]
        messages.append(sub_message)

    for idx, string in enumerate(messages):
        if idx == 0:
            await message.reply(string, mention_author=False)
        else:
            await message.channel.send(string)

def clean_discord_message(input_string):
    # Clean Discord message of any <@!123456789> tags.
    bracket_pattern = re.compile(r'<[^>]+>')
    cleaned_content = bracket_pattern.sub('', input_string)
    return cleaned_content.strip()

def extract_url(string):
    # Extract URL from a string.
    url_regex = re.compile(
        r'(?:(?:https?|ftp)://)?'
        r'(?:\S+(?::\S*)?@)?'
        r'(?:'
        r'(?!(?:10|127)(?:\.\d{1,3}){3})'
        r'(?!(?:169\.254|192\.168)(?:\.\d{1,3}){2})'
        r'(?!172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})'
        r'(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])'
        r'(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){2}'
        r'(?:\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-4]))'
        r'|'
        r'(?:www.)?'
        r'(?:[a-z\u00a1-\uffff0-9]-?)*[a-z\u00a1-\uffff0-9]+'
        r'(?:\.(?:[a-z\u00a1-\uffff]{2,}))+'
        r'(?:\.(?:[a-z\u00a1-\uffff]{2,})+)*'
        r')'
        r'(?::\d{2,5})?'
        r'(?:[/?#]\S*)?',
        re.IGNORECASE
    )
    match = re.search(url_regex, string)
    return match.group(0) if match else None

def is_youtube_url(url):
    # Check if URL is a YouTube URL.
    if url is None:
        return False
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    return re.match(youtube_regex, url) is not None


# --- Slash Commands ---

@bot.tree.command(name='createthread', description='Create a thread in which bot will respond to every message.')
async def create_thread(interaction: discord.Interaction, name: str):
    try:
        thread = await interaction.channel.create_thread(name=name, auto_archive_duration=60)
        tracked_threads.append(thread.id)
        await interaction.response.send_message(f"Thread '{name}' created! Go to <#{thread.id}> to join the thread and chat with me there.")
    except Exception as e:
        await interaction.response.send_message("❗️ Error creating thread!")

@bot.tree.command(name='help', description='Shows help(ful) info and commands for Techiee.')
async def help(interaction: discord.Interaction):
    await interaction.response.send_message(help_text)

@bot.tree.command(name='sync', description='Sync the slash commands, available to the owner only.')
async def sync(interaction: discord.Interaction):
    if interaction.user.id == discord_user_id:
        await interaction.response.defer(ephemeral=True)  # Defer since sync can take a moment
        
        # Sync globally
        synced = await bot.tree.sync()
        
        print(f'Command tree synced. Synced {len(synced)} commands globally.')
        await interaction.followup.send(f'✅ Command tree synced! Synced {len(synced)} commands globally.\n-# Note: Global sync can take up to 1 hour to fully propagate across Discord.')
    else:
        await interaction.response.send_message('You must be the owner to use this command!')

@bot.tree.command(name='thinking', description='Set the AI thinking level for reasoning depth.')
@app_commands.choices(level=[
    app_commands.Choice(name='minimal - Fastest, less reasoning', value='minimal'),
    app_commands.Choice(name='low - Fast, simple reasoning', value='low'),
    app_commands.Choice(name='medium - Balanced thinking', value='medium'),
    app_commands.Choice(name='high - Deep reasoning (default)', value='high'),
])
async def thinking(interaction: discord.Interaction, level: app_commands.Choice[str]):
    # Defer the response to prevent timeout
    await interaction.response.defer()
    
    # Determine if this is a thread or DM/tracked channel
    is_thread = interaction.channel.id in tracked_threads
    context_id = interaction.channel.id if is_thread else interaction.user.id
    
    # Get current settings or create new ones
    if is_thread:
        current_settings = thread_settings.get(context_id, default_settings.copy())
    else:
        current_settings = user_settings.get(context_id, default_settings.copy())
    
    # Update thinking level
    current_settings["thinking_level"] = level.value
    set_settings(context_id, is_thread, current_settings)
    
    scope_msg = "this thread" if is_thread else "you"
    await interaction.followup.send(f"🧠 Thinking level set to **{level.value}** for {scope_msg}.")

@bot.tree.command(name='persona', description='Set a custom persona for the AI.')
@app_commands.describe(description='The persona description (leave empty or use "default" to reset)')
async def persona(interaction: discord.Interaction, description: str = None):
    # Determine if this is a thread or DM/tracked channel
    is_thread = interaction.channel.id in tracked_threads
    context_id = interaction.channel.id if is_thread else interaction.user.id
    
    # Get current settings or create new ones
    if is_thread:
        current_settings = thread_settings.get(context_id, default_settings.copy())
    else:
        current_settings = user_settings.get(context_id, default_settings.copy())
    
    # Check if resetting to default
    if description is None or description.lower() == "default":
        current_settings["persona"] = None
        set_settings(context_id, is_thread, current_settings)
        scope_msg = "this thread" if is_thread else "you"
        await interaction.response.send_message(f"🎭 Persona reset to default for {scope_msg}.")
    else:
        current_settings["persona"] = description
        set_settings(context_id, is_thread, current_settings)
        scope_msg = "this thread" if is_thread else "you"
        await interaction.response.send_message(f"🎭 Persona set for {scope_msg}:\n> {description}")

@bot.tree.command(name='forget', description='Clear your message history with Techiee.')
async def forget(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in message_history:
        del message_history[user_id]
        await interaction.response.send_message(f"🧼 History cleared for {interaction.user.name}!")
    else:
        await interaction.response.send_message("📭 You don't have any history to clear.")


# --- Run Bot ---
bot.run(DISCORD_BOT_TOKEN)
