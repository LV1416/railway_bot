from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime

from bot.utils.pending import get_pending, clear_pending
from bot.services.equipment import process_fitment, process_add_equipment, process_removal

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split('_')
    if len(parts) < 2:
        return
        
    user_id = parts[1]
    action = parts[0]

    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Callback: action={action}, user_id={user_id}, callback_data={data}")
    
    pending = get_pending(user_id)
    if not pending:
        logger.warning(f"No pending action found for user_id={user_id}")
        await query.edit_message_text("❌ Action expired. Please send message again.")
        return
    
    logger.info(f"Found pending action: type={pending.type}, data_keys={list(pending.data.keys())}")

    if action == 'confirm':
        if pending.type == 'FITMENT':
            result = await process_fitment(pending.data, datetime.now(), pending.edits)
        elif pending.type == 'REMOVAL':
            result = await process_removal(pending.data, datetime.now(), pending.edits)
        else: # ADD_EQUIPMENT
            result = await process_add_equipment(pending.data, query.from_user.username, pending.edits)
            
        await query.edit_message_text(result, parse_mode='Markdown')
        clear_pending(user_id)
        
    elif action == 'edit':
        if pending.type == 'REMOVAL':
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Loco No", callback_data=f"editfield_{user_id}_loco_no"),
                 InlineKeyboardButton("Equipment Type", callback_data=f"editfield_{user_id}_equipment_type")],
                [InlineKeyboardButton("MFG Serial", callback_data=f"editfield_{user_id}_serial_no"),
                 InlineKeyboardButton("Removal Date", callback_data=f"editfield_{user_id}_date")],
                [InlineKeyboardButton("Overhaul Type", callback_data=f"editfield_{user_id}_overhaul_type"),
                 InlineKeyboardButton("Workshop", callback_data=f"editfield_{user_id}_workshop")],
                [InlineKeyboardButton("Remarks", callback_data=f"editfield_{user_id}_remarks")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")]
            ])
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Loco No", callback_data=f"editfield_{user_id}_loco_no"),
                 InlineKeyboardButton("Equipment Type", callback_data=f"editfield_{user_id}_equipment_type")],
                [InlineKeyboardButton("MFG Serial", callback_data=f"editfield_{user_id}_serial_no"),
                 InlineKeyboardButton("LOC Serial", callback_data=f"editfield_{user_id}_loc_serial")],
                [InlineKeyboardButton("Make", callback_data=f"editfield_{user_id}_make"),
                 InlineKeyboardButton("Mfg Date", callback_data=f"editfield_{user_id}_mfg_date")],
                [InlineKeyboardButton("Fitment Date", callback_data=f"editfield_{user_id}_date"),
                 InlineKeyboardButton("Schedule", callback_data=f"editfield_{user_id}_schedule_name")],
                [InlineKeyboardButton("Overhaul Date", callback_data=f"editfield_{user_id}_last_overhaul_date"),
                 InlineKeyboardButton("Remarks", callback_data=f"editfield_{user_id}_remarks")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")]
            ])
        await query.edit_message_text("✏️ Which field would you like to edit?", reply_markup=keyboard)
        
    elif action == 'cancel':
        clear_pending(user_id)
        await query.edit_message_text("❌ Action cancelled.")

async def edit_field_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    if len(parts) < 3:
        await query.edit_message_text("❌ Invalid edit request.")
        return
    
    user_id = parts[1]
    field = '_'.join(parts[2:])
    
    logger.info(f"Edit field: user_id={user_id}, field={field}, callback_data={query.data}")
    
    field_mapping = {
        'loco_no': 'loco_no',
        'equipment_type': 'equipment_type',
        'serial_no': 'serial_no',
        'loc_serial': 'loc_serial',
        'make': 'make',
        'mfg_date': 'mfg_date',
        'date': 'date',
        'schedule_name': 'schedule_name',
        'last_overhaul_date': 'last_overhaul_date',
        'remarks': 'remarks',
        'overhaul_type': 'overhaul_type',
        'workshop': 'workshop'
    }
    
    actual_field = field_mapping.get(field, field)
    
    pending = get_pending(user_id)
    if not pending:
        logger.warning(f"No pending action found for edit field, user_id={user_id}")
        await query.edit_message_text("❌ Action expired. Please send the message again.")
        return
    
    logger.info(f"Found pending for edit: type={pending.type}, setting editing_field={actual_field}")
    pending.data['editing_field'] = actual_field
    
    await query.edit_message_text(
        f"✏️ **Editing: {field.replace('_', ' ').title()}**\n\n"
        f"Current value: `{pending.data.get(actual_field, '-')}`\n\n"
        f"Please send the new value for this field.",
        parse_mode='Markdown'
    )
    
    context.user_data['awaiting_edit'] = True
    context.user_data['user_id'] = user_id
