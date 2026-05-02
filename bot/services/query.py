import logging

import config
from bot.utils.sheets_cache import sheets_cache
from bot.utils.formatting import format_date

logger = logging.getLogger(__name__)

from bot.services.equipment import sheet

async def get_loco_status(loco_no: str):
    try:
        loco_master = sheet.worksheet(config.SHEETS["LOCO_MASTER"])
        equip_master = sheet.worksheet(config.SHEETS["EQUIPMENT_MASTER"])
        messages_sheet = sheet.worksheet(config.SHEETS["LOCO_MESSAGES"])
        
        cell = loco_master.find(str(loco_no))
        if not cell:
            return f"❌ Loco {loco_no} not found"
        row = loco_master.row_values(cell.row)
        
        response = f"🚂 LOCO {loco_no} STATUS\n────────────────────────\n"
        # Defensive indexing
        response += f"Type: {row[1] if len(row) > 1 else '-'}\n"
        response += f"DOC: {format_date(row[2]) if len(row) > 2 else '-'}\n"
        response += f"Last Major: {row[3] if len(row) > 3 else '-'} ({format_date(row[4]) if len(row) > 4 else '-'})\n"
        response += f"Last Minor: {row[5] if len(row) > 5 else '-'} ({format_date(row[6]) if len(row) > 6 else '-'})\n"
        response += f"Next Major: {format_date(row[7]) if len(row) > 7 else '-'}\n"
        response += f"Status: {row[8] if len(row) > 8 else '-'}\n\n"
        response += "🔧 EQUIPMENT FITTED\n────────────────────────\n"
        
        all_eq = sheets_cache.get("EQUIPMENT_MASTER")
        if all_eq is None:
            all_eq = equip_master.get_all_records(head=1)
            sheets_cache.set("EQUIPMENT_MASTER", all_eq)
            
        fitted = [e for e in all_eq if str(e.get('Current_Loco', '')) == str(loco_no)]
        
        if fitted:
            for eq in fitted:
                response += f"{eq.get('Equipment_Type')}:\n"
                response += f"  MFG Serial: {eq.get('Serial_No_MFG')}\n"
                response += f"  LOC Serial: {eq.get('Serial_No_LOC')}\n"
                response += f"  Make: {eq.get('Make')}\n"
                response += f"  Mfg Date: {format_date(eq.get('Mfg_Date'))}\n"
                response += f"  Fitment: {format_date(eq.get('Fitment_Date'))}\n"
                response += f"  Last OH: {eq.get('Last_Overhaul_Type')} ({format_date(eq.get('Last_Overhaul_Date'))})\n"
                response += f"  Next Due: {format_date(eq.get('Next_Overhaul_Due'))}\n"
                response += f"  Status: {eq.get('Status')}\n"
                response += f"  Notes: {eq.get('Notes', '-')}\n\n"
        else:
            response += "No equipment fitted\n\n"
            
        response += "📝 RECENT MESSAGES\n────────────────────────\n"
        
        all_msgs = sheets_cache.get("LOCO_MESSAGES")
        if all_msgs is None:
            all_msgs = messages_sheet.get_all_records()
            sheets_cache.set("LOCO_MESSAGES", all_msgs)
            
        loco_msgs = [m for m in all_msgs if str(m.get('Loco_No', '')) == str(loco_no)]
        
        if loco_msgs:
            for msg in loco_msgs[-5:]:
                response += f"{str(msg.get('Timestamp', ''))[:10]} | {str(msg.get('Message', ''))[:80]}\n"
        else:
            response += "No recent messages\n"
            
        return response
    except Exception as e:
        logger.error(f"Error getting loco status: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"

async def get_equipment_history(serial_no: str):
    try:
        equip_master = sheet.worksheet(config.SHEETS["EQUIPMENT_MASTER"])
        history_sheet = sheet.worksheet(config.SHEETS["EQUIPMENT_HISTORY"])
        
        all_records = sheets_cache.get("EQUIPMENT_MASTER")
        if all_records is None:
            all_records = equip_master.get_all_records(head=1)
            sheets_cache.set("EQUIPMENT_MASTER", all_records)
            
        found = None
        for rec in all_records:
            if str(rec.get('Serial_No_MFG')) == str(serial_no) or str(rec.get('Serial_No_LOC')) == str(serial_no):
                found = rec
                break
                
        if not found:
            return f"❌ Equipment {serial_no} not found"
            
        response = f"🔩 EQUIPMENT DETAILS\n────────────────────────\n"
        response += f"Serial MFG: {found.get('Serial_No_MFG')}\n"
        response += f"Serial LOC: {found.get('Serial_No_LOC')}\n"
        response += f"Type: {found.get('Equipment_Type')}\n"
        response += f"Make: {found.get('Make')}\n"
        response += f"Mfg Date: {format_date(found.get('Mfg_Date'))}\n"
        response += f"Current Loco: {found.get('Current_Loco', 'STORAGE')}\n"
        response += f"Fitment Date: {format_date(found.get('Fitment_Date'))}\n"
        response += f"Last OH: {found.get('Last_Overhaul_Type')} ({format_date(found.get('Last_Overhaul_Date'))})\n"
        response += f"Next Due: {format_date(found.get('Next_Overhaul_Due'))}\n"
        response += f"Status: {found.get('Status')}\n"
        response += f"Notes: {found.get('Notes', '-')}\n\n"
        response += "📜 HISTORY (Last 10)\n────────────────────────\n"
        
        all_history = sheets_cache.get("EQUIPMENT_HISTORY")
        if all_history is None:
            all_history = history_sheet.get_all_records()
            sheets_cache.set("EQUIPMENT_HISTORY", all_history)
            
        eq_history = [h for h in all_history if str(h.get('Serial_No')) == str(serial_no)]
        
        if eq_history:
            for hist in eq_history[-10:]:
                date = format_date(hist.get('Event_Date')) if hist.get('Event_Date') else ''
                response += f"{date} | {hist.get('Event_Type')} | {hist.get('From_Loco')} -> {hist.get('To_Loco')} | {str(hist.get('Remarks', ''))[:60]}\n"
        else:
            response += "No history\n"
            
        return response
    except Exception as e:
        logger.error(f"Error getting equipment history: {e}")
        return f"❌ Error: {str(e)}"

async def process_query(data: dict):
    query_type = data.get('query_type', '')
    query_value = data.get('query_value', '')
    
    if query_type == 'LOCO_STATUS':
        return await get_loco_status(query_value)
    elif query_type == 'EQUIPMENT_STATUS':
        return await get_equipment_history(query_value)
    else:
        return "❌ Please specify a loco number or equipment serial number"

async def get_loco_status_json(loco_no: str) -> dict:
    try:
        loco_master = sheet.worksheet(config.SHEETS["LOCO_MASTER"])
        equip_master = sheet.worksheet(config.SHEETS["EQUIPMENT_MASTER"])
        messages_sheet = sheet.worksheet(config.SHEETS["LOCO_MESSAGES"])
        
        cell = loco_master.find(str(loco_no))
        if not cell:
            return {"error": f"Loco {loco_no} not found"}
        row = loco_master.row_values(cell.row)
        
        loco_info = {
            "loco_no": loco_no,
            "type": row[1] if len(row) > 1 else '-',
            "doc": format_date(row[2]) if len(row) > 2 else '-',
            "last_major": f"{row[3] if len(row) > 3 else '-'} ({format_date(row[4]) if len(row) > 4 else '-'})",
            "last_minor": f"{row[5] if len(row) > 5 else '-'} ({format_date(row[6]) if len(row) > 6 else '-'})",
            "next_major": format_date(row[7]) if len(row) > 7 else '-',
            "status": row[8] if len(row) > 8 else '-'
        }
        
        all_eq = sheets_cache.get("EQUIPMENT_MASTER")
        if all_eq is None:
            all_eq = equip_master.get_all_records(head=1)
            sheets_cache.set("EQUIPMENT_MASTER", all_eq)
            
        fitted = [e for e in all_eq if str(e.get('Current_Loco', '')) == str(loco_no)]
        
        equipment_list = []
        for eq in fitted:
            equipment_list.append({
                "type": eq.get('Equipment_Type', '-'),
                "serial_mfg": eq.get('Serial_No_MFG', '-'),
                "serial_loc": eq.get('Serial_No_LOC', '-'),
                "make": eq.get('Make', '-'),
                "mfg_date": format_date(eq.get('Mfg_Date')),
                "fitment_date": format_date(eq.get('Fitment_Date')),
                "last_oh": f"{eq.get('Last_Overhaul_Type', '-')} ({format_date(eq.get('Last_Overhaul_Date'))})",
                "next_due": format_date(eq.get('Next_Overhaul_Due')),
                "status": eq.get('Status', '-'),
                "notes": eq.get('Notes', '-')
            })
            
        all_msgs = sheets_cache.get("LOCO_MESSAGES")
        if all_msgs is None:
            all_msgs = messages_sheet.get_all_records()
            sheets_cache.set("LOCO_MESSAGES", all_msgs)
            
        loco_msgs = [m for m in all_msgs if str(m.get('Loco_No', '')) == str(loco_no)]
        
        messages_list = []
        for msg in loco_msgs[-10:]:  # Return up to 10 latest
            messages_list.append({
                "date": str(msg.get('Timestamp', ''))[:10],
                "text": str(msg.get('Message', '')),
                "user": str(msg.get('User', '-'))
            })
            
        return {
            "success": True,
            "loco_info": loco_info,
            "equipment": equipment_list,
            "messages": messages_list
        }
    except Exception as e:
        logger.error(f"Error getting loco status JSON: {e}", exc_info=True)
        return {"error": str(e)}
