# How to set Techiee up

First, grab your [Google AI Studio API Key](https://aistudio.google.com/app/apikey) and your [Discord Bot Token](https://discord.com/developers/applications), you will need these for later!

You can put channel ID(s) in which Techiee will always check for the messages and respond to them in [config.py](https://github.com/MerBudd/Techiee.py/edit/main/config.py). Otherwise, pinging Techiee, DMing Techiee or using `/createthread` will also work.

## !! WARNING: Techiee.py's config is currently set to Gemini *1.5* Pro! The API access for 1.5 isn't available to the public yet! If you don't have API access to 1.5 Pro, use 1.0 Pro instead!

You can use a hosting service like [Render](render.com) (which is free and works just fine). You can also host locally on your computer. If you host with Render, you can host 24/7.

## How to run locally
- Please make sure that you have [git](https://git-scm.com/downloads) and [Python](https://python.org/downloads) installed on your computer before proceeding!
1. Clone this repo, by opening a Terminal/Command Prompt by doing:
   ```bash
   git clone https://github.com/MerBudd/Techiee.py.git
   cd Techiee.py
   ```
2. Rename "[.env.example](https://github.com/MerBudd/Techiee.py/blob/main/.env.example)" to `.env`
3. Open `.env` and put your Google AI Studio API Key, your bot's token, and channel ID in `.env`, then save.
4. To install dependencies, do:
   ```
   pip install -U -r requirements.txt
   ```
5. To run the bot, do:
   ```
   python Techiee.py
   ```
   
## How to run in Render
- Fork this repo
- Go to [Render](https://render.com/)
- Sign up or log in
- In the dashboard, click "New", then "Web service". Then click "Next".
- If your forked repo is private, connect your GitHub account to Render and click "Connect" on the repo. If it's public, you can simply search for it
- Set the name to anything you want
- In the "Build command" section, put `pip install -U -r requirements.txt` and in the "Start command" section, put `python Techiee.py`
- Choose the free plan (it's more than enough to run Techiee)
- In the Enivronment secrets section, create 2 new secrets called `GOOGLE_AI_KEY` and `DISCORD_BOT_TOKEN`, and set their values to your Google AI Studio API Key and your Bot's token respectively
- Click "Create Web Service"

## Do 24/7 with Render
- Go to your newly created Web Service
- At the top, click the copy icon next to the blue URL to copy it (it should look something like https://webservicename.onrender.com)
- Go to [UptimeRobot](https://uptimerobot.com) and sign up or log in
- In the dashboard, click "New monitor"
- Paste the URL you copied into the "URL to monitor" field (you can set the "friendly name" to anything you want)
- Click "Create monitor"
