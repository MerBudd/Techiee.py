import os
import dotenv

dotenv.load_dotenv('.env')
dotenv.load_dotenv('.env.development')

GOOGLE_AI_KEY = os.getenv('GOOGLE_AI_KEY')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

tracked_channels = [
	# channel_id_1,
	# thread_id_2,
]

text_generation_config = {
	"temperature": 0.9,
	"top_p": 1,
	"top_k": 1,
	# "max_output_tokens": 512,
}
image_generation_config = {
	"temperature": 0.4,
	"top_p": 1,
	"top_k": 32,
	# "max_output_tokens": 512,
}
safety_settings = [
	 {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
	 {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
	 {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
	 {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

bot_template = [
	 {'role':'user','parts': ["Hello!"]},
	 {'role':'model','parts': ["Hello! I am Techiee, an experimental chatbot. Your friendly neighborhood chatbot, as one might say. How can I help?"]},
	 {'role':'user','parts': ["Who were you developed by?"]},
	 {'role':'model','parts': ["Well, I was developed by Tech and Budd, and I was built on Google's Gemini AI models."]},
]
