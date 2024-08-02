# How to set Techiee up

First, grab your [Google AI Studio API Key](https://aistudio.google.com/app/apikey) and your [Discord Bot Token](https://discord.com/developers/applications), you will need these for later!

You can put channel ID(s) in which Techiee will always check for the messages and respond to them in [config.py](https://github.com/MerBudd/Techiee.py/edit/main/config.py). Otherwise, pinging Techiee, DMing Techiee or using `/createthread` will also work.

> [!WARNING]
> Techiee.py's config is currently set to an experimental version of Gemini 1.5 Pro! If you don't want an experimental version, you can use the regular one or the other models instead! (Gemini 1.5 Flash recommended)

You can use a hosting service like [Render](render.com) (which is free and works just fine). You can also host locally on your computer. If you host with Render, you can host 24/7.

## How to run locally
- Make sure that you have [git](https://git-scm.com/downloads) and [Python](https://python.org/downloads) installed on your computer before proceeding!
1. Clone this repo, by opening a Terminal/Command Prompt and doing:
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
   
## How to run in Render
1. Fork this repo
2. Go to [Render](https://render.com/)
3. Sign up or log in
4. In the dashboard, click "New", then "Web service". Then click "Next"
5. If your forked repo is private, connect your GitHub account to Render and click "Connect" on the repo. If it's public, you can simply search for it
6. Set the name to anything you want
7. In the "Build command" section, put `pip install -U -r requirements.txt` and in the "Start command" section, put `python Techiee.py`
8. Choose the free plan (it's more than enough to run Techiee)
9. In the Enivronment secrets section, create 2 new secrets called `GEMINI_API_KEY` and `DISCORD_BOT_TOKEN`, and set their values to your Google AI Studio API Key and your Bot's token respectively
10. Click "Create Web Service"

## Do 24/7 with Render
- Go to your newly created Web Service
- At the top, click the copy icon next to the blue URL to copy it (it should look something like https://webservicename.onrender.com)
- Go to [UptimeRobot](https://uptimerobot.com) and sign up or log in
- In the dashboard, click "New monitor"
- Paste the URL you copied into the "URL to monitor" field (you can set the "friendly name" to anything you want)
- Click "Create monitor"