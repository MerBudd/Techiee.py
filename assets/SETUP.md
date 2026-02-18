# How to set Techiee up

First, grab your [Google AI Studio API Key](https://aistudio.google.com/app/apikey) and your [Discord Bot Token](https://discord.com/developers/applications), you will need these for later!

You can put channel ID(s) in which Techiee will always check for messages and respond, in [config.py](config.py). Otherwise, pinging Techiee, DMing Techiee or using `/create-thread` will also work.

You can also adjust many other settings in [config.py](config.py), such as the models to use, default thinking level, model parameters, safety settings, system prompt, help text, default prompts for different content types, and more. You should put your own Discord user ID (and any other admins) in there. This allows you to use admin-only commands like `/sync`. 

## How to run
- Make sure that you have [git](https://git-scm.com/downloads) and [Python](https://python.org/downloads) installed on your computer before proceeding!
1. Clone this repo, by opening a terminal/command prompt and running:
   ```bash
   git clone https://github.com/MerBudd/Techiee.py.git
   cd Techiee.py
   ```
2. Rename "[.env.example](https://github.com/MerBudd/Techiee.py/blob/main/.env.example)" to `.env`
3. Open `.env` and put your AI Studio / Gemini API Key(s), along with your bot's token in the appropriate fields, then save
4. To install dependencies, run:
   ```
   pip install -U -r requirements.txt
   ```
5. To run the bot, run this command:
   ```
   python Techiee.py
   ```

> [!NOTE]
> Grounding with Google Search requires a paid API tier and is disabled by default. To enable it, set `enable_google_search = True` in `config.py`.
