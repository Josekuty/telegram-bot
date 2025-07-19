#!/usr/bin/env python3
"""
Main bot runner with keep-alive functionality
"""
import asyncio
import logging
import nest_asyncio
from threading import Thread
from telegram_bot import run_bot
from keep_alive import keep_alive

# Allow nested event loops
nest_asyncio.apply()

def start_keep_alive():
    """Start the keep-alive server in a separate thread"""
    keep_alive()

def start_bot():
    """Start the Telegram bot"""
    logging.basicConfig(level=logging.INFO)
    print("Starting Telegram bot with keep-alive...")
    asyncio.run(run_bot())

if __name__ == "__main__":
    # Start keep-alive server
    keep_alive_thread = Thread(target=start_keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    
    # Start the bot
    start_bot()
