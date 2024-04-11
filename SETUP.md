# How to set Techiee up

All you'll need to do is to set the environment secrets for your [Google AI Studio API Key](https://aistudio.google.com/app/apikey) and your [Discord Bot Token](https://discord.com/developers/applications).

You need to put channel ID(s) in which Techiee will always check for the messages and respond to them in [config.py](https://github.com/MerBudd/Techiee.py/edit/main/config.py)

## !! WARNING: Techiee.py's config is currently set to Gemini *1.5* Pro! The API access for 1.5 isn't available to the public yet! If you don't have API access to 1.5 Pro, use 1.0 Pro instead!

You can use a hosting service like [Render](render.com) (which is free and works just fine). You can also host locally on your computer. If you host with Render, you can host 24/7.

## How to run locally
- Clone this repo
- Rename "[.env.example](https://github.com/MerBudd/Techiee.py/blob/main/.env.example)" to ".env" (without the quotes)
- Put your tokens and keys in .env
- Open a terminal in the directory where you cloned the repo to, and run "python Techiee.py" (without the quotes). Or, if you're fancy and use a code editor, you can open the Techiee.py file and just click "Run" (whereever that button may be in your editor)

## How to run in Render
- Fork this repo
- Go to [Render](https://render.com/)
- Sign up or log in
- In the dashboard, click "New", then "Web service". Then click "Next".
- If your forked repo is private, connect your GitHub account to Render and click "Connect" on the repo. If it's public, you can simply search for it.
- You can set the name to anything you want.
- In the "Start command" section, put "python Techiee.py" (without the quotes)
- At the bottom, choose the free plan (it's more than enough to run Techiee)
- At the VERY bottom, in the Enivronment secrets section, create 2 new secrets called "GOOGLE_AI_KEY" and "DISCORD_BOT_TOKEN" (without the quotes), and set their values to your Google AI Studio API Key and your Bot's token respectively (Where to grab them is listed at the very top of this file)
- Click "Create Web Service"

## Do 24/7 with Render
- Go to your newly created Web Service
- At the top, click the copy icon next to the blue URL to copy it (it should look something like https://webservicename.onrender.com)
- Go to [UptimeRobot](https://uptimerobot.com) and sign up or log in
- In the dashboard, click "New monitor"
- Paste the URL you copied into the "URL to monitor" field (you can set the "friendly name" to anything you want)
- Click "Create monitor"
