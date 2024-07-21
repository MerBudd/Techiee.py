# Dependencies
import os
import google.generativeai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import dotenv
from dotenv import load_dotenv
load_dotenv()

# Environment variables
gemini_api_key = os.getenv('GEMINI_API_KEY')
discord_bot_token = os.getenv('DISCORD_BOT_TOKEN')

# Name of the Gemini model. Currently, the Gemini 1.5 Pro API is only in limited access, so use gemini-1.5-flash if you don't have access
gemini_model = "gemini-1.5-pro-latest"

# AI generation configs, these are some pretty advanced settings, don't mess around with these if you don't know what you're doing
generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

# Safety settings, the thresholds can be BLOCK_NONE, BLOCK_MEDIUM_AND_ABOVE, BLOCK_LOW_AND_ABOVE, or HARM_BLOCK_THRESHOLD_UNSPECIFIED (which uses the default block threshold set by Google)
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

# System prompt, essentially what the AI needs to know about itself / where it's in / what it does, and the instructions you give it etc. It will never forget this, unlike the message histroy which has a limit you can set
system_instruction = "You are Techiee, an experimental chatbot. You were developed by Discord users Tech (@techgamerexpert) and Budd (@merbudd), and they built you on Google's Gemini AI models."

# The list of tracked channels (the Discord IDs of said channels), in which Techiee will always respond to messages
tracked_channels = [
	1208874114916425828,
]

# Default summary prompt if the message is just a URL and nothing else
default_url_prompt = "Summarize the following by giving me 5 bullet points"

# The maximum amount of messages to be saved in the message history before the oldest message gets deleted, set to 0 to disable message history
max_history = 30