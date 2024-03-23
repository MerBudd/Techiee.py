from flask import Flask,render_template
from threading import Thread

app = Flask(__name__)

@app.route('/')
def index():
    return "Webserver is on, bot should be alive and 24/7 should work."

def run():
  app.run(host='0.0.0.0',port=8080)

def keep_alive():  
    t = Thread(target=run)
    t.start()
