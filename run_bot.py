#!/usr/bin/env python3
"""
Standalone script to run the Telegram bot
"""
import asyncio
import logging
import nest_asyncio
from telegram_bot import run_bot

# Allow nested event loops
nest_asyncio.apply()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Starting Telegram bot...")
    asyncio.run(run_bot())
