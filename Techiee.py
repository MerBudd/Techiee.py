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
from google.genai.types import Tool, GenerateContentConfig, Part, Content

from config import *

GEMINI_API_KEY = gemini_api_key
DISCORD_BOT_TOKEN = discord_bot_token
MAX_HISTORY = max_history

message_history = {}
tracked_threads = []

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
        type=discord.ActivityType.listening,
        name="your every command and being the best Discord chatbot!"
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
        
        async with message.channel.typing():
            # Check for image attachments
            if message.attachments:
                for attachment in message.attachments:
                    print(f"New Attachment Message FROM: {message.author.name} : {cleaned_text}")
                    
                    # Image processing
                    if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                        print("Processing Image")
                        response_text = await process_image_attachment(attachment, cleaned_text)
                        await split_and_send_messages(message, response_text, 1900)
                        return
                    
                    # PDF and text file processing
                    elif attachment.filename.lower().endswith('.pdf') or attachment.filename.lower().endswith('.txt'):
                        print(f"Processing {'PDF' if attachment.filename.lower().endswith('.pdf') else 'Text'} File")
                        response_text = await process_file_attachment(attachment, cleaned_text)
                        await split_and_send_messages(message, response_text, 1900)
                        return
                    
                    else:
                        # Try to process as generic text file
                        print("Processing as generic attachment")
                        response_text = await process_file_attachment(attachment, cleaned_text)
                        await split_and_send_messages(message, response_text, 1900)
                        return
            
            # Text-only message processing
            else:
                print(f"New Text Message FROM: {message.author.name} : {cleaned_text}")
                
                # Check for keywords to reset history
                if any(keyword in cleaned_text for keyword in ["RESET HISTORY", "FORGET HISTORY", "CLEAR HISTORY", "CLEAN HISTORY"]):
                    if message.author.id in message_history:
                        del message_history[message.author.id]
                    await message.channel.send("🧼 History Reset for user: " + str(message.author.name))
                    return
                
                # Check for URLs
                url = extract_url(cleaned_text)
                if url is not None:
                    print(f"Got URL: {url}")
                    if is_youtube_url(url):
                        print("Processing YouTube Video")
                        response_text = await process_youtube_url(url, cleaned_text)
                    else:
                        print("Processing Website URL")
                        response_text = await process_website_url(url, cleaned_text)
                    await split_and_send_messages(message, response_text, 1900)
                    return
                
                # Regular text conversation with history
                if MAX_HISTORY == 0:
                    response_text = await generate_response_with_text(cleaned_text)
                    await split_and_send_messages(message, response_text, 1900)
                    return
                
                # Add user's question to history
                update_message_history(message.author.id, cleaned_text)
                response_text = await generate_response_with_text(get_formatted_message_history(message.author.id))
                # Add AI response to history
                update_message_history(message.author.id, response_text)
                await split_and_send_messages(message, response_text, 1900)


# --- Response Generation Functions ---

async def generate_response_with_text(message_text):
    """Generate a response for text-only input."""
    try:
        response = client.models.generate_content(
            model=gemini_model,
            contents=message_text,
            config=GenerateContentConfig(
                system_instruction=system_instruction,
                safety_settings=safety_settings,
                **generation_config
            )
        )
        return response.text
    except Exception as e:
        return "❌ Exception: " + str(e)


async def process_image_attachment(attachment, user_text):
    """Process an image attachment using the Files API."""
    try:
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
                config=GenerateContentConfig(
                    system_instruction=system_instruction,
                    safety_settings=safety_settings,
                    **generation_config
                )
            )
            return response.text
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return "❌ Exception: " + str(e)


async def process_file_attachment(attachment, user_text):
    """Process PDF or text file attachments using the Files API."""
    try:
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
                config=GenerateContentConfig(
                    system_instruction=system_instruction,
                    safety_settings=safety_settings,
                    **generation_config
                )
            )
            return response.text
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return "❌ Exception: " + str(e)


async def process_youtube_url(url, user_text):
    """Process YouTube video URL using FileData."""
    try:
        prompt = user_text.replace(url, "").strip() if user_text else default_url_prompt
        
        response = client.models.generate_content(
            model=gemini_model,
            contents=Content(
                parts=[
                    Part(file_data=types.FileData(file_uri=url)),
                    Part(text=prompt)
                ]
            ),
            config=GenerateContentConfig(
                system_instruction=system_instruction,
                safety_settings=safety_settings,
                **generation_config
            )
        )
        return response.text
    except Exception as e:
        return "❌ Exception: " + str(e)


async def process_website_url(url, user_text):
    """Process website URL using URL context tool."""
    try:
        prompt = user_text if user_text else f"{default_url_prompt} {url}"
        
        # If user provided custom text, make sure the URL is included
        if user_text and url not in user_text:
            prompt = f"{user_text} {url}"
        
        response = client.models.generate_content(
            model=gemini_model,
            contents=prompt,
            config=GenerateContentConfig(
                tools=[Tool(url_context=types.UrlContext())],
                system_instruction=system_instruction,
                safety_settings=safety_settings,
                **generation_config
            )
        )
        return response.text
    except Exception as e:
        return "❌ Exception: " + str(e)


# --- Message History ---

def update_message_history(user_id, text):
    """Update message history for a user."""
    if user_id in message_history:
        message_history[user_id].append(text)
        if len(message_history[user_id]) > MAX_HISTORY:
            message_history[user_id].pop(0)
    else:
        message_history[user_id] = [text]

def get_formatted_message_history(user_id):
    """Get formatted message history for a user."""
    if user_id in message_history:
        return '\n\n'.join(message_history[user_id])
    else:
        return "No messages found for this user."


# --- Utility Functions ---

async def split_and_send_messages(message_system, text, max_length):
    """Split long messages and send them sequentially."""
    messages = []
    for i in range(0, len(text), max_length):
        sub_message = text[i:i+max_length]
        messages.append(sub_message)

    for string in messages:
        await message_system.channel.send(string)

def clean_discord_message(input_string):
    """Clean Discord message of any <@!123456789> tags."""
    bracket_pattern = re.compile(r'<[^>]+>')
    cleaned_content = bracket_pattern.sub('', input_string)
    return cleaned_content.strip()

def extract_url(string):
    """Extract URL from a string."""
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
    """Check if URL is a YouTube URL."""
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
        await bot.tree.sync(guild=interaction.guild)
        print('Command tree synced.')
        await interaction.response.send_message('Command tree synced.')
    else:
        await interaction.response.send_message('You must be the owner to use this command!')


# --- Run Bot ---
bot.run(DISCORD_BOT_TOKEN)
