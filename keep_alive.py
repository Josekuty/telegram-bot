"""
Keep-alive server to maintain Replit deployment
"""
from flask import Flask
from threading import Thread
import time

app = Flask(__name__)

@app.route('/')
def home():
    return "Instagram Bot is running!"

@app.route('/health')
def health():
    return {"status": "healthy", "service": "instagram-bot"}

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

if __name__ == "__main__":
    keep_alive()
    # Keep the main thread alive
    while True:
        time.sleep(60)
