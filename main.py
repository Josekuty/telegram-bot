import os
from telegram.ext import Updater

TOKEN = os.getenv("TOKEN")

updater = Updater(TOKEN)
