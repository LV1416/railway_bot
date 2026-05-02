from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from bot.services.loco import process_schedule
from bot.services.query import get_equipment_history, get_loco_status_json
from bot.services.reports import upcoming_overhauls, list_storage
from bot.services.equipment import process_fitment, process_removal, process_add_equipment, sheet
from bot.utils.sheets_cache import sheets_cache
from parser.railway_parser import RailwayParser
import config

api_app = FastAPI(title="Loco Management API")
parser = RailwayParser(use_ai=True)

# Setup CORS for the frontend to easily fetch data
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ParseMessageData(BaseModel):
    message: str

class FitmentData(BaseModel):
    loco_no: str
    equipment_type: str
    serial_no: str
    date: Optional[str] = None
    make: Optional[str] = None
    mfg_date: Optional[str] = None
    loc_serial: Optional[str] = None
    remarks: Optional[str] = ""

class RemovalData(BaseModel):
    loco_no: str
    serial_no: str
    date: Optional[str] = None
    overhaul_type: Optional[str] = None
    workshop: Optional[str] = None
    remarks: Optional[str] = ""

class AddEquipmentData(BaseModel):
    equipment_type: str
    serial_no: str
    status: Optional[str] = "STORAGE" # New field for Web UI status
    make: Optional[str] = None
    mfg_date: Optional[str] = None
    loc_serial: Optional[str] = None
    remarks: Optional[str] = ""

@api_app.get("/status/{loco_no}")
async def api_loco_status(loco_no: str):
    try:
        res = await get_loco_status_json(loco_no)
        if "error" in res:
            raise HTTPException(status_code=404, detail=res["error"])
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/equipment/{serial}")
async def api_equipment_history(serial: str):
    try:
        res = await get_equipment_history(serial)
        return {"data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/reports/upcoming")
async def api_upcoming_overhauls(days: int = 30):
    try:
        res = await upcoming_overhauls(days)
        return {"data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/storage")
async def api_list_storage():
    try:
        res = await list_storage()
        return {"data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_app.get("/equipment_all")
async def api_equipment_all():
    try:
        equip_master = sheet.worksheet(config.SHEETS["EQUIPMENT_MASTER"])
        all_records = sheets_cache.get("EQUIPMENT_MASTER")
        if all_records is None:
            all_records = equip_master.get_all_records(head=1)
            sheets_cache.set("EQUIPMENT_MASTER", all_records)
        return {"data": all_records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_app.post("/fitment")
async def api_fitment(data: FitmentData):
    try:
        payload = data.model_dump()
        res = await process_fitment(payload, datetime.now())
        
        if res.startswith("✅"):
            log_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            eq = payload.get('equipment_type', '')
            sn = payload.get('serial_no', '')
            loco = payload.get('loco_no', 'N/A')
            rmks = payload.get('remarks', '')
            log_msg = f"FITMENT: Fitted {eq} (Serial: {sn}) on Loco {loco}. Details: {rmks}"
            messages_sheet = sheet.worksheet(config.SHEETS["LOCO_MESSAGES"])
            messages_sheet.append_row([log_ts, loco, log_msg, "WebUI"])
            
        return {"message": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_app.post("/removal")
async def api_removal(data: RemovalData):
    try:
        payload = data.model_dump()
        res = await process_removal(payload, datetime.now())
        
        if res.startswith("✅"):
            log_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sn = payload.get('serial_no', '')
            loco = payload.get('loco_no', 'N/A')
            rmks = payload.get('remarks', '')
            log_msg = f"REMOVAL: Removed Equipment (Serial: {sn}) from Loco {loco}. Details: {rmks}"
            messages_sheet = sheet.worksheet(config.SHEETS["LOCO_MESSAGES"])
            messages_sheet.append_row([log_ts, loco, log_msg, "WebUI"])
            
        return {"message": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_app.post("/add_equipment")
async def api_add_equipment(data: AddEquipmentData):
    try:
        payload = data.model_dump()
        payload['query_type'] = 'ADD_EQUIPMENT'
        res = await process_add_equipment(payload, "WebUser", "WebUI")
        
        if res.startswith("✅"):
            log_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            eq = payload.get('equipment_type', '')
            sn = payload.get('serial_no', '')
            st = payload.get('status', 'STORAGE')
            rmks = payload.get('remarks', '')
            log_msg = f"ADD: Added {eq} (Serial: {sn}) to {st}. Details: {rmks}"
            messages_sheet = sheet.worksheet(config.SHEETS["LOCO_MESSAGES"])
            messages_sheet.append_row([log_ts, "N/A", log_msg, "WebUI"])
            
        return {"message": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_app.post("/parse_message")
async def api_parse_message(data: ParseMessageData):
    try:
        parsed = parser.parse_message(data.message, "WebUser", "WebUI")
        if not parsed:
            raise HTTPException(status_code=400, detail="Could not extract data from message")
        return {"parsed": parsed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
