import os
import requests
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, Application
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

# MongoDB Setup
MONGO_URI = "mongodb+srv://rahul:rahul@cluster0.tmhfkw.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = AsyncIOMotorClient(MONGO_URI)
db = client['space_monitoring']

# Telegram Bot Token (replace with your actual bot token)
telegram_token = "8040785759:AAHEtdMrtST5LyfaYlVpUPzPzp6_LxekDnQ"

# Initialize Telegram Application
application = Application.builder().token(telegram_token).build()

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to handle /start command
async def start(update: Update, context):
    user_id = update.message.from_user.id
    await update.message.reply("Welcome! Please set your Hugging Face credentials using /set.")

# Function to handle /set command where users input their Hugging Face details
async def set_credentials(update: Update, context):
    user_id = update.message.from_user.id
    if len(context.args) != 2:
        await update.message.reply("Please provide the correct format: `/set hf_token=<YOUR_HF_TOKEN> hf_username=<YOUR_USERNAME>`")
        return

    hf_token, hf_username = context.args

    # Save user information to MongoDB
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"hf_token": hf_token, "hf_username": hf_username}},
        upsert=True
    )

    await update.message.reply(f"Credentials saved. Now you can fetch your spaces with /fetch")

# Function to handle /fetch command to get spaces from Hugging Face API
async def fetch_spaces(update: Update, context):
    user_id = update.message.from_user.id
    user = await db.users.find_one({"_id": user_id})

    if not user:
        await update.message.reply("You need to set your credentials first. Use /set to provide them.")
        return

    hf_token = user["hf_token"]
    hf_username = user["hf_username"]

    # Fetch spaces from Hugging Face using their API
    headers = {"Authorization": f"Bearer {hf_token}"}
    url = f"https://huggingface.co/api/spaces/{hf_username}/"  # Fetch all spaces for the user

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            # Successfully fetched the spaces
            spaces_data = response.json()

            if not spaces_data:
                await update.message.reply("No spaces found for this user.")
                return

            # Show spaces to the user with inline buttons
            keyboard = [
                [InlineKeyboardButton(space["name"], callback_data=space["url"]) for space in spaces_data]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply("Choose a space to monitor:", reply_markup=reply_markup)

        else:
            await update.message.reply(f"Failed to fetch spaces: {response.status_code}. Check your credentials.")
    except requests.exceptions.RequestException as e:
        await update.message.reply(f"Error fetching spaces: {e}")

# Function to handle the button clicks (start monitoring a space)
async def button(update: Update, context):
    query = update.callback_query
    space_url = query.data
    user_id = query.from_user.id
    await query.answer()

    # Here, you would start monitoring the space and save it to MongoDB
    # For now, we'll just confirm the monitoring
    user = await db.users.find_one({"_id": user_id})

    if user:
        monitored_spaces = user.get("monitored_spaces", [])
        monitored_spaces.append({"name": space_url, "url": space_url})
        await db.users.update_one({"_id": user_id}, {"$set": {"monitored_spaces": monitored_spaces}})

    await query.edit_message_text(f"Monitoring {space_url} now. You will receive updates every 6 hours.")

    # Start periodic updates (every 6 hours)
    asyncio.create_task(send_periodic_updates(user_id, space_url))

# Function to send periodic updates every 6 hours (status of the monitored space)
async def send_periodic_updates(user_id, space_url):
    while True:
        # Simulate checking the space status (this can be improved)
        status = check_space_status(space_url)

        # Send status update to the user
        user = await db.users.find_one({"_id": user_id})

        if user:
            message = f"Status Update for {space_url}:\nStatus: {status}"
            await application.bot.send_message(user_id, message)

        # Sleep for 6 hours (21600 seconds)
        await asyncio.sleep(21600)

# Function to simulate checking space status (This should be improved)
def check_space_status(space_url):
    # Here you would actually check the space's status
    # For simplicity, we return a mock status (either 'Running' or 'Down')
    # You can replace this with actual HTTP requests to the space's URL
    return "Running"  # Simulating that the space is always running

# Register the handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("set", set_credentials, pass_args=True))
application.add_handler(CommandHandler("fetch", fetch_spaces))
application.add_handler(CallbackQueryHandler(button))

# Run the bot
async def main():
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
