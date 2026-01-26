# How to set Techiee up

First, grab your [Google AI Studio API Key](https://aistudio.google.com/app/apikey) and your [Discord Bot Token](https://discord.com/developers/applications), you will need these for later!

You can put channel ID(s) in which Techiee will always check for the messages and respond to them in [config.py](https://github.com/MerBudd/Techiee.py/edit/main/config.py). Otherwise, pinging Techiee, DMing Techiee or using `/createthread` will also work.

> [!WARNING]
> Techiee.py's config is currently set to an experimental version of Gemini 3 Flash! If you don't want an experimental version, you can use other models instead.

## How to run
- Make sure that you have [git](https://git-scm.com/downloads) and [Python](https://python.org/downloads) installed on your computer before proceeding!
1. Clone this repo, by opening a terminal/command prompt and doing:
   ```bash
   git clone https://github.com/MerBudd/Techiee.py.git
   cd Techiee.py
   ```
2. Rename "[.env.example](https://github.com/MerBudd/Techiee.py/blob/main/.env.example)" to `.env`
3. Open `.env` and put your Google AI Studio API Key, along with your bot's token in there, then save
4. To install dependencies, do:
   ```
   pip install -U -r requirements.txt
   ```
5. To run the bot, do:
   ```
   python Techiee.py
   ```

> [!NOTE]
> Grounding with Google Search currently requires a paid API tier and is disabled by default in Techiee. Please un-comment line 197 in `Techiee.py` and line 39 in `config.py` to enable it.