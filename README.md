# <img src="https://github.com/MerBudd/Techiee.js/assets/82082386/43cc9180-c22f-4418-8949-9834a5066089" width="40" height="40" align=top> Techiee.py

## <img src="https://github.com/MerBudd/Techiee.js/assets/82082386/43cc9180-c22f-4418-8949-9834a5066089" width="30" height="30" align=top> Techiee is an advanced Discord AI Chatbot powered by Google's Gemini models.

This is the Python version of Techiee! It has been completely rewritten to support the latest Gemini 3 models and multimodal capabilities.

## What is Techiee?

Techiee is a capable Discord chatbot built on Google's Gemini models. Techiee is multimodal, which means it can understand text, images, documents, websites, and even YouTube videos together, directly within your Discord server.

## Key Features

- **🧠 Advanced Reasoning**: Use the `/thinking` command to adjust the AI's reasoning depth (Minimal to High).
- **🖼️ Multimodal Support**: Send images, PDFs, or text files and Techiee will analyze them.
- **🌐 Web & Video Integration**: Paste a website URL or a YouTube link, and Techiee can summarize or discuss the content.
- **💬 Smart Memory**: Maintains per-user and per-thread message history for natural conversations.
- **🎭 Persistent Personas**: Set a custom personality with `/persona` that stays active even after history resets.
- **🧵 Threads**: Create dedicated chat spaces with `/createthread`.
- **🔍 Google Search Grounding**: Support for real-time web search (requires paid plan, disabled by default).

## Configuration

You can tweak all bot settings, including safety filters, model parameters, and tracked channels, inside the [config.py](config.py) file.

For detailed installation instructions, check out [SETUP.md](SETUP.md).

## Commands

- `/help`: Shows available commands and bot information.
- `/createthread <name>`: Starts a new thread where Techiee will respond to every message.
- `/thinking <level>`: Sets the AI's reasoning level (minimal, low, medium, high).
- `/persona <description>`: Sets a custom personality. Use `/persona default` to reset.
- `/sync`: Syncs slash commands (Owner only).
- **Reset History**: Send a message containing `CLEAR HISTORY` (all caps) to wipe your current conversation memory.

### Features to-do

- Imagen / Native image gen support
---
*Developed by Budd (@merbudd) and Tech (@techgamerexpert).*