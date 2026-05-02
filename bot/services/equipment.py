import logging
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

import config
from bot.utils.sheets_cache import sheets_cache

logger = logging.getLogger(__name__)

# Reusing the init approach from old app.py
def _init_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        # Fallback to local file for dev if needed
        return gspread.service_account(filename=config.CREDENTIALS_FILE).open(config.SHEET_NAME)
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(config.SHEET_NAME)

sheet = _init_google_sheets()

async def process_add_equipment(data: dict, username: str, edits: list[str] = None):
    try:
        equip_type = data.get('equipment_type', '').upper()
        serial_no = data.get('serial_no', '')
        make = data.get('make', '')
        mfg_date = data.get('mfg_date', '')
        remarks = data.get('remarks', '')
        loc_serial = data.get('loc_serial', '')

        if not equip_type or not serial_no:
            return "❌ Missing equipment type or serial number"
            
        if edits:
            remarks += f" [Edited: {', '.join(edits)}]"

        equip_master = sheet.worksheet(config.SHEETS["EQUIPMENT_MASTER"])
        # Check cache first for existing records check
        all_records = sheets_cache.get("EQUIPMENT_MASTER")
        if all_records is None:
            all_records = equip_master.get_all_records(head=1)
            sheets_cache.set("EQUIPMENT_MASTER", all_records)
            
        for rec in all_records:
            if str(rec.get('Serial_No_MFG', '')) == str(serial_no) or str(rec.get('Serial_No_LOC', '')) == str(serial_no):
                return f"❌ Equipment {serial_no} already exists."

        new_row = [
            serial_no, loc_serial, equip_type, make, mfg_date,
            "", "", "", "", "", "STORAGE", remarks[:200] if remarks else ""
        ]
        equip_master.append_row(new_row)
        sheets_cache.invalidate("EQUIPMENT_MASTER") # invalidate cache after write

        return f"✅ Equipment added to **STORAGE**\n🔧 Type: {equip_type}\n📌 Serial: {serial_no}\n🏭 Make: {make or '-'}\n📅 Mfg Date: {mfg_date or '-'}\n📍 LOC Serial: {loc_serial or '-'}"
    except Exception as e:
        logger.error(f"Error adding equipment: {e}")
        return f"❌ Error adding equipment: {str(e)}"

async def process_fitment(data: dict, timestamp: datetime, edits: list[str] = None):
    try:
        loco_no = data.get('loco_no')
        equipment_type = data.get('equipment_type', 'UNKNOWN').upper()
        serial_no = data.get('serial_no')
        fitment_date = data.get('date') or timestamp.strftime('%d-%m-%Y')
        remarks = data.get('remarks', '')
        make = data.get('make', '')
        mfg_date = data.get('mfg_date', '')
        loc_serial = data.get('loc_serial', '')
        last_overhaul_date = data.get('last_overhaul_date', '')
        schedule_name = data.get('schedule_name', '')

        if not loco_no or not serial_no:
            return "❌ Missing loco number or equipment serial number"
            
        if edits:
            remarks += f" [Edited: {', '.join(edits)}]"

        equip_master = sheet.worksheet(config.SHEETS["EQUIPMENT_MASTER"])
        
        all_records = sheets_cache.get("EQUIPMENT_MASTER")
        if all_records is None:
            all_records = equip_master.get_all_records(head=1)
            sheets_cache.set("EQUIPMENT_MASTER", all_records)

        found_row = None
        for idx, rec in enumerate(all_records, start=2):
            if str(rec.get('Serial_No_MFG', '')) == str(serial_no) or str(rec.get('Serial_No_LOC', '')) == str(serial_no):
                found_row = idx
                break

        created = False
        if not found_row:
            new_row = [
                serial_no, loc_serial, equipment_type, make, mfg_date,
                "", "", last_overhaul_date, schedule_name, "",
                "STORAGE", f"Auto-created: {remarks[:100]}"
            ]
            equip_master.append_row(new_row)
            created = True
            found_row = len(all_records) + 2

        # ---------------- BATCH UPDATE ----------------
        # We need to update cells F through K. F is col 6, K is col 11
        # Range F:K = Current_Loco, Fitment_Date, Last_Overhaul_Date, Last_Overhaul_Type, Next_Overhaul_Due, Status
        
        # Determine loco class roughly to help with overhaul cycle calculation
        loco_class = None
        # Basic heuristic: 3xxxx = WAP7, 22xxx=WAP4, 31xxx=WAG9 etc.
        if loco_no.startswith('22'): loco_class = 'WAP4'
        elif loco_no.startswith('30'): loco_class = 'WAP5'
        elif loco_no.startswith('31') or loco_no.startswith('32') or loco_no.startswith('41'): loco_class = 'WAG9'
        elif loco_no.startswith('37') or loco_no.startswith('39'): loco_class = 'WAP7'

        next_due_str = ""
        if last_overhaul_date:
            try:
                cycle_days = config.get_overhaul_days(equipment_type, loco_class)
                due_date = datetime.strptime(last_overhaul_date, '%d-%m-%Y') + timedelta(days=cycle_days)
                next_due_str = due_date.strftime('%d-%m-%Y')
            except Exception as e:
                logger.warning(f"Could not calculate due date from {last_overhaul_date}: {e}")

        # If it was just created, we still need to update the fitment fields
        # Better to update just the columns we need
        updates = []
        cell_updates = [
            {'range': f'F{found_row}', 'values': [[loco_no]]},
            {'range': f'G{found_row}', 'values': [[fitment_date]]},
            {'range': f'K{found_row}', 'values': [["IN_SERVICE"]]}
        ]
        if loc_serial:
            cell_updates.append({'range': f'B{found_row}', 'values': [[loc_serial]]})
        if last_overhaul_date:
            cell_updates.append({'range': f'H{found_row}', 'values': [[last_overhaul_date]]})
            cell_updates.append({'range': f'I{found_row}', 'values': [[schedule_name]]})
            if next_due_str:
                cell_updates.append({'range': f'J{found_row}', 'values': [[next_due_str]]})
        
        equip_master.batch_update(cell_updates)

        history_sheet = sheet.worksheet(config.SHEETS["EQUIPMENT_HISTORY"])
        history_sheet.append_row([
            serial_no, fitment_date, "FIT", "STORAGE", loco_no, "", schedule_name, remarks
        ])
        
        sheets_cache.invalidate("EQUIPMENT_MASTER")

        if created:
            return f"✅ **Equipment created and fitted successfully!**\n\n🔧 Type: {equipment_type}\n📌 Serial: {serial_no}\n📍 LOC Serial: {loc_serial or '-'}\n🏭 Make: {make or '-'}\n📅 Mfg Date: {mfg_date or '-'}\n🚂 Fitted to Loco: {loco_no}\n📅 Fitment Date: {fitment_date}\n📝 Notes: {remarks[:100]}\n\nStatus: **IN_SERVICE**"
        else:
            return f"✅ **Equipment fitted successfully!**\n\n🔧 Equipment: {equipment_type} ({serial_no})\n🚂 Loco: {loco_no}\n📅 Fitment Date: {fitment_date}\n📝 Notes: {remarks[:100]}\n\nStatus updated to **IN_SERVICE**."
    except Exception as e:
        logger.error(f"Error in fitment: {e}", exc_info=True)
        return f"❌ Error during fitment: {str(e)}"

async def process_removal(data: dict, timestamp: datetime, edits: list[str] = None):
    try:
        loco_no = data.get('loco_no')
        serial_no = data.get('serial_no')
        removal_date = data.get('date') or timestamp.strftime('%d-%m-%Y')
        overhaul_type = data.get('overhaul_type', '')
        workshop = data.get('workshop', '')
        remarks = data.get('remarks', '')
        
        if edits:
            remarks += f" [Edited: {', '.join(edits)}]"
            
        if not serial_no:
            return "❌ No equipment serial number found"

        equip_master = sheet.worksheet(config.SHEETS["EQUIPMENT_MASTER"])
        
        all_records = sheets_cache.get("EQUIPMENT_MASTER")
        if all_records is None:
            all_records = equip_master.get_all_records(head=1)
            sheets_cache.set("EQUIPMENT_MASTER", all_records)

        found_row = None
        equipment_type = "UNKNOWN"
        for idx, rec in enumerate(all_records, start=2):
            if str(rec.get('Serial_No_MFG', '')) == str(serial_no) or str(rec.get('Serial_No_LOC', '')) == str(serial_no):
                found_row = idx
                equipment_type = str(rec.get('Equipment_Type', 'UNKNOWN'))
                break

        if not found_row:
            return f"❌ Equipment {serial_no} not found"

        next_due_str = ""
        if removal_date:
            try:
                # Basic loco class inference from loco_no
                loco_class = None
                if loco_no:
                    if loco_no.startswith('22'): loco_class = 'WAP4'
                    elif loco_no.startswith('30'): loco_class = 'WAP5'
                    elif loco_no.startswith('31') or loco_no.startswith('32') or loco_no.startswith('41'): loco_class = 'WAG9'
                    elif loco_no.startswith('37') or loco_no.startswith('39'): loco_class = 'WAP7'
                    
                cycle_days = config.get_overhaul_days(equipment_type, loco_class)
                due_date = datetime.strptime(removal_date, '%d-%m-%Y') + timedelta(days=cycle_days)
                next_due_str = due_date.strftime('%d-%m-%Y')
            except Exception as e:
                logger.warning(f"Could not calculate due date from {removal_date}: {e}")

        # ---------------- BATCH UPDATE ----------------
        cell_updates = [
            {'range': f'H{found_row}', 'values': [[removal_date]]},
            {'range': f'I{found_row}', 'values': [[overhaul_type]]},
            {'range': f'F{found_row}', 'values': [[""]]}, # Clear Current_Loco
            {'range': f'G{found_row}', 'values': [[""]]}, # Clear Fitment_Date
            {'range': f'K{found_row}', 'values': [["UNDER_OVERHAUL"]]}
        ]
        if next_due_str:
            cell_updates.append({'range': f'J{found_row}', 'values': [[next_due_str]]})
            
        equip_master.batch_update(cell_updates)

        history_sheet = sheet.worksheet(config.SHEETS["EQUIPMENT_HISTORY"])
        history_sheet.append_row([serial_no, removal_date, "REMOVE", loco_no or "", "WORKSHOP", workshop, overhaul_type, remarks])
        
        sheets_cache.invalidate("EQUIPMENT_MASTER")

        return f"✅ Equipment Removed Successfully\n🔧 Serial: {serial_no}\n📍 From Loco: {loco_no or 'Unknown'}\n📅 Removal Date: {removal_date}\n🔨 Overhaul: {overhaul_type or 'Not specified'}\nStatus: UNDER_OVERHAUL"
    except Exception as e:
        logger.error(f"Error processing removal: {e}")
        return f"❌ Error recording removal: {str(e)}"
