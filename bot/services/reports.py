from datetime import datetime
import logging

import config
from bot.utils.sheets_cache import sheets_cache

logger = logging.getLogger(__name__)

from bot.services.equipment import sheet

async def upcoming_overhauls(days: int = 30) -> str:
    """Generate a report of equipment due for overhaul in the next X days."""
    try:
        equip_master = sheet.worksheet(config.SHEETS["EQUIPMENT_MASTER"])
        
        all_records = sheets_cache.get("EQUIPMENT_MASTER")
        if all_records is None:
            all_records = equip_master.get_all_records(head=1)
            sheets_cache.set("EQUIPMENT_MASTER", all_records)
            
        now = datetime.now()
        target_date = now + datetime.timedelta(days=days) if hasattr(datetime, 'timedelta') else now + __import__('datetime').timedelta(days=days)
        
        due_list = []
        for rec in all_records:
            next_due_str = str(rec.get('Next_Overhaul_Due', '')).strip()
            if not next_due_str:
                continue
            
            try:
                due_dt = datetime.strptime(next_due_str, '%d-%m-%Y')
                # Include items already overdue as well (due_dt < target_date)
                if due_dt <= target_date:
                    days_diff = (due_dt - now).days
                    due_list.append({
                        'type': rec.get('Equipment_Type', '-'),
                        'serial': rec.get('Serial_No_MFG') or rec.get('Serial_No_LOC') or '-',
                        'loco': rec.get('Current_Loco') or 'Storage',
                        'due': next_due_str,
                        'days': days_diff
                    })
            except Exception:
                pass
                
        if not due_list:
            return f"✅ No equipment due for overhaul in the next {days} days."
            
        # Sort by days remaining (most overdue first)
        due_list.sort(key=lambda x: x['days'])
        
        res = f"🔔 **Equipment Due for Overhaul (Next {days} Days)**\n\n"
        for item in due_list:
            status = f"{item['days']} days" if item['days'] > 0 else f"**OVERDUE {-item['days']} days**"
            res += f"• **{item['type']}** {item['serial']} — Due: {item['due']} ({status})\n"
            res += f"  Loco: {item['loco']}\n\n"
            
        return res
    except Exception as e:
        logger.error(f"Error generating upcoming report: {e}", exc_info=True)
        return f"❌ Error generating report: {str(e)}"

async def list_storage() -> str:
    """Generate a list of all equipment currently in STORAGE."""
    try:
        equip_master = sheet.worksheet(config.SHEETS["EQUIPMENT_MASTER"])
        
        all_records = sheets_cache.get("EQUIPMENT_MASTER")
        if all_records is None:
            all_records = equip_master.get_all_records(head=1)
            sheets_cache.set("EQUIPMENT_MASTER", all_records)
            
        storage_items = [r for r in all_records if str(r.get('Status', '')).upper() == 'STORAGE']
        
        if not storage_items:
            return "📦 No equipment currently in storage."
            
        # Group by type
        grouped = {}
        for item in storage_items:
            eq_type = item.get('Equipment_Type', 'UNKNOWN')
            if eq_type not in grouped:
                grouped[eq_type] = []
            grouped[eq_type].append(item)
            
        res = f"📦 **Equipment in Storage: {len(storage_items)} items**\n\n"
        for eq_type, items in grouped.items():
            res += f"**{eq_type} ({len(items)})**\n"
            for item in items:
                serial = item.get('Serial_No_MFG') or item.get('Serial_No_LOC') or '-'
                make = item.get('Make', '-')
                res += f"• {serial} (Make: {make})\n"
            res += "\n"
            
        return res
    except Exception as e:
        logger.error(f"Error listing storage: {e}")
        return f"❌ Error retrieving storage list: {str(e)}"
