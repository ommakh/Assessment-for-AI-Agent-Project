import os
import google.generativeai as genai
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
import base64
import asyncio
import logging
from datetime import datetime, timezone
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from textblob import TextBlob
from analytics import fetch_analytics_summary, generate_dashboard

# Load environment variables
load_dotenv()


genai.configure(api_key=os.getenv("GEMINI_API"))
model = genai.GenerativeModel("gemini-1.5-flash")
Token=os.getenv("TELEGRAM_TOKEN")
client = AsyncIOMotorClient(os.getenv("MONGO_URL"))
db = client['db1']
users_collection = db["users"]
chat_collection = db["chat_history"]
file_collection = db["file_metadata"]


# Logging
logging.basicConfig(level=logging.INFO)

# MongoDB Setup (Use AsyncIOMotorClient)


async def user_exists(chat_id: int) -> bool:
    user = await users_collection.find_one({"chat_id": chat_id})
    return user is not None  # Corrected async handling

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if not await user_exists(chat_id):
        await users_collection.insert_one({
            "chat_id": chat_id,
            "first_name": user.first_name,
            "username": user.username,
            "phone_number": None,
            "registered_at": datetime.now(timezone.utc)  # Fixed datetime
        })
        await request_phone_number(update)
    else:
        await update.message.reply_text("You are already registered!")
    await update.message.reply_text(
        "You're all set! 🎉\n\n"
        "Type /analytics to see your user analytics"
        "/dashboard for your detailed dashboard"
        "Type /websearch to perform a web search"
    )

async def request_phone_number(update: Update):
    contact_btn = KeyboardButton(" Share Name and Phone Number ", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_btn]], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Click the button below to share your Name and phone number:",
        reply_markup=reply_markup
    )

async def save_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    phone_number = update.message.contact.phone_number

    await users_collection.update_one(
        {"chat_id": chat_id},
        {"$set": {"phone_number": phone_number}}
    )
    await update.message.reply_text(" Thanks! Your Name and phone number has been saved.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    try:
        try:
            response = await asyncio.to_thread(model.generate_content, user_text)
            ai_reply = response.text

            # Sentiment Analysis
            sentiment = TextBlob(user_text).sentiment.polarity
            sentiment_label = (
                "Positive " if sentiment > 0.2 else
                "Negative " if sentiment < -0.2 else
                "Neutral "
            )
        except Exception as e:
            sentiment_label = "Error"

        response = await asyncio.to_thread(model.generate_content, user_text)
        ai_reply = response.text
    except Exception as e:
        ai_reply = f"Sorry, I encountered an error: {str(e)}"
        sentiment_label = "Error"

    # Store conversation (Fixed incorrect use of `await`)
    await chat_collection.insert_one({
        "chat_id": chat_id,
        "user_message": user_text,
        "ai_response": ai_reply,
        "sentiment": sentiment_label,
        "timestamp": datetime.now(timezone.utc)  # Fixed datetime
    })
    await update.message.reply_text(ai_reply)


# Configure logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure this model is initialized elsewhere

async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    message = update.message

    try:
        # Identify the correct file type
        if message.photo:
            file_id = message.photo[-1].file_id
            mime_type = "image/jpeg"  # Default for Telegram photos
        elif message.document:
            file_id = message.document.file_id
            mime_type = message.document.mime_type or "application/octet-stream"
        else:
            return

        # Download file data
        file = await context.bot.get_file(file_id)
        image_data = await file.download_as_bytearray()

        # Convert image data to base64
        encoded_image = base64.b64encode(image_data).decode("utf-8")

        # Gemini API expects a specific structure for image input
        image_part = {
            "mime_type": mime_type,
            "data": encoded_image
        }

        # Generate description using Gemini API
        prompt = "Describe this image in detail."
        response = model.generate_content([prompt, image_part])

        # Extract response text safely
        description = response.text if hasattr(response, "text") else "Could not analyze image."

        # Store file details in MongoDB
        await file_collection.insert_one({
            "chat_id": chat_id,
            "file_id": file_id,
            "description": description,
            "timestamp": datetime.now(timezone.utc),
        })

        # Reply with the analysis result
        await update.message.reply_text(f"📸 Image analyzed:\n\n{description}")

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        await update.message.reply_text(f" Error processing image: {str(e)}")


async def send_analytics_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = await fetch_analytics_summary(users_collection, chat_collection)
    await update.message.reply_text(summary, parse_mode="Markdown")

async def send_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dashboard_path = await generate_dashboard(users_collection, chat_collection)
    await update.message.reply_photo(photo=open(dashboard_path, "rb"), caption="Your Analytics Dashboard")

async def web_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter your search query.")

def main():
    application = Application.builder().token(Token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("websearch", web_search))
    application.add_handler(MessageHandler(filters.CONTACT, save_phone_number))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_files))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("analytics", send_analytics_summary))
    application.add_handler(CommandHandler("dashboard", send_dashboard))

    application.run_polling()

if __name__ == "__main__":
    main()



