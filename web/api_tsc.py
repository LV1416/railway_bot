from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from bot.services.tsc import (
    receive_tsc, issue_tsc, remove_tsc, send_to_blw,
    get_dashboard_stats, get_running_tscs, get_available_tscs,
    get_blw_account, get_tsc_history, get_loco_tsc_history,
    get_premature_failures, get_waiting_dispatch, get_register, get_alerts,
)

tsc_api_app = FastAPI(title="TSC Management API")

tsc_api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ── Models ──
class ReceiveData(BaseModel):
    tsc_no: str
    received_from: str = ""
    received_date: Optional[str] = ""
    pl_no: Optional[str] = ""
    oh_type: Optional[str] = "Overhauling"
    letter_no: Optional[str] = ""
    remarks: Optional[str] = ""

class IssueData(BaseModel):
    tsc_no: str
    loco_no: str
    issue_date: Optional[str] = ""
    cause_of_change: Optional[str] = ""
    remarks: Optional[str] = ""

class RemoveData(BaseModel):
    tsc_no: str
    removal_date: Optional[str] = ""
    cause: Optional[str] = ""
    condition: Optional[str] = "FAILED"  # GOOD / FAILED / OVERDUE
    next_action: Optional[str] = ""      # SEND_TO_BLW / KEEP_FOR_FITMENT
    remarks: Optional[str] = ""

class SendBLWData(BaseModel):
    tsc_no: str
    dispatch_date: Optional[str] = ""
    pl_no: Optional[str] = ""
    oh_type: Optional[str] = "Overhauling"
    dispatch_letter_no: Optional[str] = ""
    warranty_no: Optional[str] = ""
    remarks: Optional[str] = ""


# ── GET Endpoints ──
@tsc_api_app.get("/dashboard")
async def api_dashboard():
    try:
        stats = await get_dashboard_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.get("/running")
async def api_running():
    try:
        data = await get_running_tscs()
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.get("/available")
async def api_available():
    try:
        data = await get_available_tscs()
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.get("/blw_account")
async def api_blw_account():
    try:
        data = await get_blw_account()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.get("/history/{tsc_no}")
async def api_tsc_history(tsc_no: str):
    try:
        data = await get_tsc_history(tsc_no)
        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.get("/loco_history/{loco_no}")
async def api_loco_history(loco_no: str):
    try:
        data = await get_loco_tsc_history(loco_no)
        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.get("/premature_failures")
async def api_premature_failures():
    try:
        data = await get_premature_failures()
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@tsc_api_app.get("/waiting_dispatch")
async def api_waiting_dispatch():
    try:
        data = await get_waiting_dispatch()
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.get("/alerts")
async def api_alerts():
    try:
        data = await get_alerts()
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.get("/register/{name}")
async def api_register(name: str, fy: str = None):
    try:
        res = await get_register(name, fy)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST Endpoints ──
@tsc_api_app.post("/receive")
async def api_receive(data: ReceiveData):
    try:
        res = await receive_tsc(data.model_dump())
        return {"message": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.post("/issue")
async def api_issue(data: IssueData):
    try:
        res = await issue_tsc(data.model_dump())
        return {"message": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.post("/remove")
async def api_remove(data: RemoveData):
    try:
        res = await remove_tsc(data.model_dump())
        return {"message": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@tsc_api_app.post("/send_blw")
async def api_send_blw(data: SendBLWData):
    try:
        res = await send_to_blw(data.model_dump())
        return {"message": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
