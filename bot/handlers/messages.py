from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from parser.railway_parser import RailwayParser
from bot.utils.pending import get_pending
from bot.utils.formatting import build_preview, build_removal_preview

import config
import logging
logger = logging.getLogger(__name__)

# Let's import the same sheet from services equipment to reuse connection logic
from bot.services.equipment import sheet

parser = RailwayParser(use_ai=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)

    # Edit mode: user is responding to an edit request
    if context.user_data.get('awaiting_edit') and context.user_data.get('user_id') == user_id:
        await receive_edit_value(update, context)
        return

    text = update.message.text
    username = update.message.from_user.username or "user"
    system_time = datetime.now()

    parsed = parser.parse_message(text, user_id, username)
    messages_sheet = sheet.worksheet(config.SHEETS["LOCO_MESSAGES"])

    # Log message
    loco_no = parsed.get('data', {}).get('loco_no')
    extracted_date = parsed.get('data', {}).get('date')
    if extracted_date:
        try:
            log_dt = datetime.strptime(extracted_date, '%d-%m-%Y')
            log_ts = log_dt.strftime('%Y-%m-%d')
        except:
            log_ts = system_time.strftime('%Y-%m-%d %H:%M:%S')
    else:
        log_ts = system_time.strftime('%Y-%m-%d %H:%M:%S')
    # Create detailed 1-liner msg
    log_msg = parsed.get('data', {}).get('one_liner_summary')
    msg_type = parsed.get('type', 'GENERAL')
    
    if not log_msg:
        # Fallback if AI didn't return one_liner_summary
        eq = parsed.get('data', {}).get('equipment_type', '')
        sn = parsed.get('data', {}).get('serial_no', '')
        if msg_type == 'FITMENT':
            log_msg = f"FITMENT: {eq} ({sn}) fitted. Details: {text}"
        elif msg_type == 'REMOVAL':
            log_msg = f"REMOVAL: {eq} ({sn}) removed. Details: {text}"
        elif msg_type == 'ADD_EQUIPMENT':
            log_msg = f"ADD: {eq} ({sn}) added. Details: {text}"
        elif msg_type == 'SCHEDULE':
            sch = parsed.get('data', {}).get('schedule_name', '')
            log_msg = f"SCHEDULE: {sch}. Details: {text}"
        else:
            log_msg = f"INFO: {text}"
            
    # Run log operation in background or don't block
    messages_sheet.append_row([log_ts, loco_no or 'N/A', log_msg, username])

    # Avoid circular import at module load
    from bot.utils.pending import set_pending
    from bot.services.loco import process_schedule
    from bot.services.query import process_query

    msg_type = parsed.get('type')
    
    if msg_type in ['FITMENT', 'ADD_EQUIPMENT']:
        set_pending(user_id, msg_type, parsed['data'], text)
        preview = await build_preview(msg_type, parsed['data'])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{user_id}"),
             InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{user_id}"),
             InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")]
        ])
        await update.message.reply_text(preview, reply_markup=keyboard, parse_mode='Markdown')
        
    elif msg_type == 'REMOVAL':
        # Added to confirmation flow
        set_pending(user_id, msg_type, parsed['data'], text)
        preview = await build_removal_preview(parsed['data'])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{user_id}"),
             InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{user_id}"),
             InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")]
        ])
        await update.message.reply_text(preview, reply_markup=keyboard, parse_mode='Markdown')
        
    elif msg_type == 'SCHEDULE':
        result = await process_schedule(parsed['data'])
        await update.message.reply_text(result)
        
    elif msg_type == 'QUERY':
        result = await process_query(parsed['data'])
        await update.message.reply_text(result)
        
    else:
        if loco_no:
            await update.message.reply_text(f"✅ Message logged for Loco {loco_no}")
        else:
            await update.message.reply_text("✅ Message logged (No loco number found)")

async def receive_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_edit'):
        return
    
    user_id = context.user_data.get('user_id')
    if not user_id:
        await update.message.reply_text("❌ Session expired. Please send the message again.")
        context.user_data['awaiting_edit'] = False
        return
    
    pending = get_pending(user_id)
    if not pending:
        await update.message.reply_text("❌ Action expired. Please send the message again.")
        context.user_data['awaiting_edit'] = False
        return
    
    # Store edit in pending action dict, not the dataclass attributes directly since pending.data is dict
    field = pending.data.get('editing_field')
    if not field:
        await update.message.reply_text("❌ No field selected for editing.")
        context.user_data['awaiting_edit'] = False
        return
    
    new_value = update.message.text.strip()
    old_value = pending.data.get(field, "-")
    
    # Update the pending data with new value
    pending.data[field] = new_value
    
    # Track the edit
    pending.edits.append(f"{field}: {old_value}->{new_value}")
    
    # Build updated preview
    if pending.type == 'REMOVAL':
        preview = await build_removal_preview(pending.data)
    else:
        preview = await build_preview(pending.type, pending.data)
    
    # Create keyboard with Confirm and Edit More buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{user_id}"),
         InlineKeyboardButton("✏️ Edit More", callback_data=f"edit_{user_id}")]
    ])
    
    safe_field = escape_markdown(field.replace('_', ' ').title(), version=1)
    safe_value = escape_markdown(new_value, version=1)
    await update.message.reply_text(
        f"✅ Field *{safe_field}* updated to: `{safe_value}`\n\n{preview}",
        reply_markup=keyboard, parse_mode='Markdown'
    )
    
    # Reset edit mode
    context.user_data['awaiting_edit'] = False
    context.user_data['user_id'] = None
