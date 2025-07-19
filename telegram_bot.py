import os
import logging
import instaloader
import tempfile
import shutil
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from app import extract_shortcode, download_instagram_content

# Setup bot token
TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me a public Instagram reel or post URL, and I’ll download it!")


# Handle Instagram links
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not ("instagram.com/reel/" in text or "instagram.com/p/" in text):
        await update.message.reply_text(
            "⚠️ Please send a valid Instagram reel/post URL.")
        return

    await update.message.reply_text("⏳ Downloading the reel...")

    try:
        video_file, error = download_instagram_content(text)
        if video_file:
            await update.message.reply_video(video=open(video_file, "rb"))
            shutil.rmtree(os.path.dirname(video_file), ignore_errors=True)
        else:
            await update.message.reply_text(f"❌ {error}")
    except Exception as e:
        logging.exception("Download error:")
        await update.message.reply_text(
            "⚠️ Something went wrong while downloading the reel.")


# Main bot function
async def run_bot():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Telegram bot is running...")
    await application.run_polling()
