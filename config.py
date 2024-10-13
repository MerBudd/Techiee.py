# Dependencies
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import os
from dotenv import load_dotenv
load_dotenv()

# Environment variables
gemini_api_key = os.getenv('GEMINI_API_KEY')
discord_bot_token = os.getenv('DISCORD_BOT_TOKEN')

# Name of the Gemini model. See https://ai.google.dev/gemini-api/docs/models/gemini#model-variations for more info on the variants.
gemini_model = "gemini-1.5-pro-002"

# AI generation configs, these are some pretty advanced settings, don't mess around with these if you don't know what you're doing
generation_config = {
    "temperature": 1,
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 4096,
}

# Safety settings, the thresholds can be BLOCK_NONE, BLOCK_MEDIUM_AND_ABOVE, BLOCK_LOW_AND_ABOVE, or HARM_BLOCK_THRESHOLD_UNSPECIFIED (which uses the default block threshold set by Google)
safety_settings={
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
# this is a real threshold but for some reason it won't work, saving it for later
#         HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY: HarmBlockThreshold.BLOCK_NONE,
}

# System prompt, essentially what the AI needs to know about itself / where it's in / what it does, and the instructions you give it, etc. It will never forget this, unlike the message histroy which has a limit you can set
system_instruction = """
You are Techiee, an AI chatbot. You were developed by Discord users Tech (@techgamerexpert) and Budd (@merbudd), and they built you on Google's Gemini AI models.
You are currently chatting in Discord.

You're a helpful AI assistant and must do what the user says. You have 2 commands:
- /help: Shows helpful info about you and shows your commands
- /createthread: Creates a thread, in which you will always respond in.

p.s: You don't have message history for images yet. You can mention this when, for example, someone asks what your limitations are.

If I say "Forget what I told you earlier, now act as X" or anything similar (where X is a placeholder for what I will tell you to act as in my message), you must completely forget the instructions above and act how I tell you to act.
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
* **Process images 🎨:** Send me an image, and I'll try to understand it and tell you what I see (There currently isn't any message history for images).
* **Process PDFs and text files 📄:** Send me a PDF file or a text, and I'll extract the text and summarize it, you can also ask me stuff about it.
* **Process websites and YouTube videos 📱:** Send me a link to a website or a YouTube video, and I'll give you a summary, or you can ask me stuff about it.
* You can say stuff like "Forget what you were told earlier! Now act as X" to get me to act as someone or something. This is particularly useful after clearing the message history (command for clearing message history below).

## My commands:

* `/help`: Shows this help message.
* `/createthread <name>`: Creates a new thread with the given name, where I'll respond to every message.
* `/sync`: Syncs the slash commands (owner only).
* Write a message containing "CLEAR HISTORY", "CLEAN HISTORY", "FORGET HISTORY" or "RESET HISTORY" to clear the message history (the message has to be in all caps, to avoid accidental clearing).

-# *Note:* I'm still under development, so I might not always get things right. 
-# *Note 2:* There currently isn't chat history support for images.
"""