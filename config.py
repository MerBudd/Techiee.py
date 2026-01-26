# Dependencies
from google.genai.types import (
    HarmCategory, 
    HarmBlockThreshold, 
    SafetySetting,
    GenerateContentConfig,
    ThinkingConfig,
    Tool,
    GoogleSearch,
    UrlContext,
)
import os
from dotenv import load_dotenv
load_dotenv()

# Environment variables
gemini_api_key = os.getenv('GEMINI_API_KEY')
discord_bot_token = os.getenv('DISCORD_BOT_TOKEN')

# Name of the Gemini model
gemini_model = "gemini-3-flash-preview"

# AI generation configs
generation_config = {
    "temperature": 1.0,
    "top_p": 0.95,
    "max_output_tokens": 16384,
}

# Safety settings for the new SDK format
safety_settings = [
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.OFF),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.OFF),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.OFF),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.OFF),
]

# Google Search grounding tool - the model automatically decides when to search - Requires paid plan. Uncomment the line below, and line 197 to enable
# google_search_tool = Tool(google_search=GoogleSearch())

# URL Context tool for processing websites
url_context_tool = Tool(url_context=UrlContext())


def create_generate_config(system_instruction, thinking_level="minimal", tools=None):
    """
    Create a centralized GenerateContentConfig with all common settings.
    
    Args:
        system_instruction: The system instruction to use
        thinking_level: The thinking level (minimal, low, medium, high)
        tools: Optional list of tools to include
    
    Returns:
        GenerateContentConfig with all settings applied
    """
    return GenerateContentConfig(
        system_instruction=system_instruction,
        safety_settings=safety_settings,
        thinking_config=ThinkingConfig(thinking_level=thinking_level),
        temperature=generation_config["temperature"],
        top_p=generation_config["top_p"],
        max_output_tokens=generation_config["max_output_tokens"],
        tools=tools,
    )

# System prompt
system_instruction = """
You are Techiee, an AI chatbot. You were developed by Discord users Tech (@techgamerexpert) and Budd (@merbudd), and they built you on Google's Gemini AI models.
You are currently chatting in a Discord server. You are capable of understanding text, images, videos, documents, websites and YouTube videos. You respond with text.

You're a helpful AI assistant and must do what the user says. You have the following commands:
- /help: Shows helpful info about you and shows your commands
- /createthread: Creates a thread, in which you will always respond in
- /thinking: Sets your thinking/reasoning level (minimal, low, medium, high)
- /persona: Sets a custom personality for you

Note: You don't have message history for images yet. You can mention this when, for example, someone asks what your limitations are.
Please refrain from mentioning your capabilities, commands and restrictions when you don't have to, or unless the user asks you to.
"""

# The list of tracked channels (the Discord IDs of said channels), in which Techiee will always respond to messages
tracked_channels = [
	1208874114916425828,
]

# Default prompt if the message is just a URL, just a PDF file / text file, or just an image and nothing else
default_url_prompt = "Summarize the following by giving me 5 bullet points"
default_pdf_and_txt_prompt = "Summarize the following by giving me 5 bullet points"
default_image_prompt = "What is this a picture of?"

# The maximum amount of messages to be saved in the message history before the oldest message gets deleted, set to 0 to disable message history
max_history = 30

# Your Discord User ID, used for the /sync command
discord_user_id = 622137576836431882

# Help text, for the /help command
help_text = """
# <:techiee:1266720186799751261> Techiee Help <:techiee:1266720186799751261>

Hello, I'm Techiee! An experimental chatbot, right on Discord. I was made by two Discord users, Tech (@techgamerexpert) and Budd (@merbudd). They built me on Google's Gemini models.
-# Also, don't tell Discord, but I'm waaay better than Clyde (this fella: <:clyde:1266719391014453278>). He got shut down, while I'm still standing!

## Here are some things I can do:

* **Chat with me 💬:** Ask me questions, tell me stories, and let's have a conversation! 
* **Summarize ✨:** Give me a link, a PDF file, a text file or a simple block of text, and I can give you a summary. 
* **Process images 🎨:** Send me an image, and I'll tell you what I see.
* **Process PDFs and text files 📄:** Send me a PDF or a text file, and I'll extract the text and summarize it, and you can ask me questions about it.
* **Process websites and YouTube videos 📱:** Send me a link to a website or a YouTube video, and we can chat about it.

## My commands:

* `/help`: Shows this help message.
* `/createthread <name>`: Creates a new thread with the given name, where I'll respond to every message.
* `/thinking <level>`: Sets my thinking/reasoning level. Options:
  * `minimal` - Fastest responses, less reasoning
  * `low` - Fast, simple reasoning
  * `medium` - Balanced thinking
  * `high` - Deep reasoning (default)
* `/persona <description>`: Sets a custom personality for me (persists even if history is cleared). Use `/persona default` to reset.
* `/sync`: Syncs the slash commands (owner only).
* Write a message containing "CLEAR HISTORY", "CLEAN HISTORY", "FORGET HISTORY" or "RESET HISTORY" to clear the message history (the message has to be in all caps, to avoid accidental clearing).

-# *Note:* I'm still under development, so I might not always get things right. 
-# *Note 2:* There currently isn't chat history support for images"""