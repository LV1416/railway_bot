import logging

import config
from bot.utils.sheets_cache import sheets_cache

logger = logging.getLogger(__name__)

# Let's import the same sheet initialized instance to reuse
from bot.services.equipment import sheet

async def process_schedule(data: dict):
    try:
        loco_master = sheet.worksheet(config.SHEETS["LOCO_MASTER"])
        loco_no = data.get('loco_no')
        if not loco_no:
            return "❌ No loco number found"
            
        cell = loco_master.find(loco_no)
        if not cell:
            return f"❌ Loco {loco_no} not found"
            
        row_num = cell.row
        schedule_type = data.get('schedule_type', '')
        schedule_name = data.get('schedule_name', '')
        schedule_date = data.get('schedule_date', '')
        next_due = data.get('next_due', '')
        updates = []
        
        cell_updates = []
        if schedule_type == 'MAJOR' and schedule_name:
            cell_updates.append({'range': f'D{row_num}', 'values': [[schedule_name]]})
            if schedule_date:
                cell_updates.append({'range': f'E{row_num}', 'values': [[schedule_date]]})
            if next_due:
                cell_updates.append({'range': f'H{row_num}', 'values': [[next_due]]})
            updates.append(f"Major {schedule_name} on {schedule_date}")
            
        elif schedule_type == 'MINOR' and schedule_name:
            cell_updates.append({'range': f'F{row_num}', 'values': [[schedule_name]]})
            if schedule_date:
                cell_updates.append({'range': f'G{row_num}', 'values': [[schedule_date]]})
            updates.append(f"Minor {schedule_name} on {schedule_date}")
            
        if updates:
            loco_master.batch_update(cell_updates)
            sheets_cache.invalidate("LOCO_MASTER")
            return f"✅ Loco {loco_no} schedule updated: {', '.join(updates)}"
        else:
            return "⚠️ Could not parse schedule information"
            
    except Exception as e:
        logger.error(f"Error processing schedule: {e}")
        return f"❌ Error updating schedule: {str(e)}"
