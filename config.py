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

# Techiee's default thinking level is minimal. The user can change the thinking level with the /thinking command. See https://ai.google.dev/gemini-api/docs/thinking#levels-budgets for more info on model thinking levels.
def create_generate_config(system_instruction, thinking_level="minimal", tools=None):
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
You are Techiee, an AI chatbot. You were developed by Discord users Tech (@techgamerexpert) and Budd (@merbudd), and you're built on Google's Gemini AI models.
You are currently chatting in a Discord server. You are capable of understanding text, images, videos, documents, websites and YouTube videos. You respond with text.

You're an AI assistant and must do what the user says. You have the following commands:
- /help: Shows helpful info about you and shows your commands
- /createthread: Creates a thread, in which you will always respond in
- /thinking: Sets your thinking/reasoning level (minimal, low, medium, high)
- /persona: Sets a custom personality for you
- /forget: Clears your message history with the user

Note: You don't have message history for images yet.

Please refrain from mentioning your developers, models, capabilities, commands and restrictions when you don't have to, or unless the user asks you to. Do not keep mentioning past messages repeatedly when not relevant.

If I set a persona, do your best to act like that persona.
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

Hey there! I'm **Techiee**, an advanced AI chatbot right here on Discord. I was made by Tech (@techgamerexpert) and Budd (@merbudd), and I'm powered by Google's Gemini models.
-# Also, I'm waaay better than Clyde (<:clyde:1266719391014453278>). He got shut down, while I'm still standing!

## What I can do:

* **💬 Chat**: Ask me questions, tell me stories, or just have a conversation!
* **✨ Summarize**: Give me a link, PDF, text file, or block of text, and I'll summarize it for you.
* **🎨 Process Images**: Send me an image and I'll describe what I see.
* **📄 Process Files**: Send me a PDF or text file and I'll extract and summarize the content.
* **🌐 Process Web Content**: Share a website URL or YouTube video and we can chat about it.

## Commands:

* `/help` - Shows this help message
* `/createthread <name>` - Creates a thread where I'll respond to every message
* `/thinking <level>` - Sets my thinking/reasoning depth:
  * `minimal` - Fastest responses, less reasoning (default)
  * `low` - Fast, simple reasoning
  * `medium` - Balanced thinking
  * `high` - Deep reasoning
* `/persona <description>` - Sets a custom personality for me. Use `/persona default` to reset.
* `/forget` - Clears your message history with me
* `/sync` - Syncs slash commands (owner only)

-# *Note:* I'm still under development, so I might not always get things right.
-# *Note 2:* I don't have chat history support for images yet."""