# How to set Techiee up

All you'll need to do is to set the environment secrets for the Discord Channel ID, your [Google AI Studio API Key](https://aistudio.google.com/app/apikey) and your [Discord Bot Token](https://discord.com/developers/applications).

You can use a hosting service like [Render](render.com) (which is free and works just fine). You can also host locally on your computer. If you host with Render, you can host 24/7.

grab your web server URL, and then use the keep_alive.py file to run it 24/7 with UptimeRobot (you can find detailed tutorials online). We can't use Replit (at least, if you want to host it 24/7 for FREE) because they killed their webservers. You can pay Replit to get it running 24/7 with their new "Deployments" if you want.

## How to run locally

- Rename [".env.example"](https://github.com/MerBudd/Techiee.py/blob/main/.env.example) to ".env"
- Put your tokens and keys in .env

## How to run in Render (and do 24/7)
- Go to [Render](https://render.com/)
- Sign up or log in
- In the dashboard, click "New", then "Web service"
- Click "Next"
- If your repo is private, connect your GitHUb account to Render and choose it. If it's public, you can simply search for it.
- In the "Start command" section, put "python Techiee.py" (without the quotes)
- At the bottom, choose the free plan (it's more than enough to run Techiee)
- athe the VERY bottom, in the Enivronment secrets section, create 2 new secrets called "GOOGLE_AI_KEY" and "DISCORD_BOT_TOKEN" (without the quotes), and set their values to your Google AI Studio API Key and your Bot's token respectively (I listed where to grab them at the very top of this file)

!!I'LL UPDATE THIS FILE LATER!!!!!
