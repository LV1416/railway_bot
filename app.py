import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

import config
from web.api import api_app
from web.api_tsc import tsc_api_app
from bot.handlers.commands import (
    start, help_command, status_command, equipment_command, 
    schedule_command, addequipment_command, report_command, list_command
)
from bot.handlers.messages import handle_message
from bot.handlers.callbacks import callback_handler, edit_field_handler
from bot.handlers.tsc_commands import (
    tsc_summary_command, tsc_running_command, 
    tsc_available_command, tsc_blw_command, tsc_status_command
)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Telegram Application
tg_app = Application.builder().token(config.BOT_TOKEN).build()

# Register command handlers
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("help", help_command))
tg_app.add_handler(CommandHandler("status", status_command))
tg_app.add_handler(CommandHandler("equipment", equipment_command))
tg_app.add_handler(CommandHandler("schedule", schedule_command))
tg_app.add_handler(CommandHandler("addequipment", addequipment_command))
tg_app.add_handler(CommandHandler("report", report_command))
tg_app.add_handler(CommandHandler("list", list_command))

# TSC Specific Commands
tg_app.add_handler(CommandHandler("tsc_summary", tsc_summary_command))
tg_app.add_handler(CommandHandler("tsc_running", tsc_running_command))
tg_app.add_handler(CommandHandler("tsc_available", tsc_available_command))
tg_app.add_handler(CommandHandler("tsc_blw", tsc_blw_command))
tg_app.add_handler(CommandHandler("tsc_status", tsc_status_command))

# Register callback query handlers (for inline buttons)
tg_app.add_handler(CallbackQueryHandler(callback_handler, pattern='^(confirm|edit|cancel)_.*'))
tg_app.add_handler(CallbackQueryHandler(edit_field_handler, pattern='^editfield_.*'))

# Register text message handler
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# FastAPI Lifespan to manage Telegram Bot
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run the Telegram Bot polling in the background
    await tg_app.initialize()
    await tg_app.start()
    # Ensure it handles updates asynchronously
    await tg_app.updater.start_polling()
    logger.info("🤖 Telegram Bot started polling...")
    
    yield
    
    # Shutdown: Stop the Telegram Bot gracefully
    logger.info("Stopping Telegram Bot...")
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()

# Create main FastAPI application
app = FastAPI(lifespan=lifespan)

# Mount the API endpoints from web.api
app.mount("/api/tsc", tsc_api_app)
app.mount("/api", api_app)

# Mount static files for CSS/JS
# Calculate absolute path for static directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "web", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def serve_ui():
    """Serve the main Web UI"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/tsc")
async def serve_tsc_dashboard():
    """Serve the TSC Management Dashboard"""
    return FileResponse(os.path.join(STATIC_DIR, "tsc_dashboard.html"))

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    # Run uvicorn programmatically for local dev
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
