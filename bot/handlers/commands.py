from telegram import Update
from telegram.ext import ContextTypes

from bot.services.query import get_loco_status, get_equipment_history
from bot.services.loco import process_schedule
from bot.services.reports import upcoming_overhauls, list_storage

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚂 Railway Equipment Tracking Bot.\nSend /help for commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/status <loco_no> - Get loco status\n"
        "/equipment <serial> - Get equipment history\n"
        "/schedule ... - Update loco schedule\n"
        "/addequipment ... - Add new equipment to storage\n"
        "/report [days] - Upcoming overhauls\n"
        "/list storage - List equipment in storage\n"
        "\nOr just type natural language messages for fitment, removal, etc."
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /status <loco_no>")
        return
    result = await get_loco_status(context.args[0])
    await update.message.reply_text(result)

async def equipment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /equipment <serial>")
        return
    result = await get_equipment_history(' '.join(context.args))
    await update.message.reply_text(result)

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 4:
        await update.message.reply_text("Usage: /schedule <loco_no> <MAJOR/MINOR> <type> <date> [next_due]")
        return
    data = {
        'loco_no': context.args[0],
        'schedule_type': context.args[1].upper(),
        'schedule_name': context.args[2].upper(),
        'schedule_date': context.args[3]
    }
    if len(context.args) > 4 and context.args[4] == 'next_due' and len(context.args) > 5:
        data['next_due'] = context.args[5]
    result = await process_schedule(data)
    await update.message.reply_text(result)

async def addequipment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please use natural language: 'Add equipment MPH serial 123 Make Flowwell Mfg 01-2020'")

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    days = 30
    if context.args and context.args[0].isdigit():
        days = int(context.args[0])
    elif context.args and context.args[0] == "upcoming" and len(context.args) > 1 and context.args[1].isdigit():
        days = int(context.args[1])
        
    result = await upcoming_overhauls(days)
    await update.message.reply_text(result, parse_mode='Markdown')

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0].lower() != 'storage':
        await update.message.reply_text("Usage: /list storage")
        return
    result = await list_storage()
    await update.message.reply_text(result, parse_mode='Markdown')
