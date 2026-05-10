import logging
from datetime import datetime, timedelta
from math import floor

import config
from bot.services.equipment import sheet
from bot.utils.sheets_cache import sheets_cache

logger = logging.getLogger(__name__)

DATE_FMT = "%d-%m-%Y"


def _today_str():
    return datetime.now().strftime(DATE_FMT)


def _parse_date(s):
    if not s:
        return None
    for fmt in (DATE_FMT, "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except Exception:
            continue
    return None


def standardize_fy(fy):
    if not fy: return ""
    fy = str(fy).strip().upper().replace("FY-", "")
    if len(fy) == 5: # e.g. 22-23
        return f"20{fy}"
    if len(fy) == 9: # e.g. 2022-2023
        return f"{fy[:5]}{fy[7:]}"
    return fy

def _get_fy(dt=None):
    dt = dt or datetime.now()
    if dt.month >= 4:
        fy = f"{dt.year}-{str(dt.year+1)[2:]}"
    else:
        fy = f"{dt.year-1}-{str(dt.year)[2:]}"
    return standardize_fy(fy)


def _ws(name):
    return sheet.worksheet(config.SHEETS[name])


HEADER_ROWS = {
    "TSC_RECEIVE": 8,
    "TSC_BLW_DISPATCH": 8
}

def _all(name):
    cached = sheets_cache.get(name)
    if cached is None:
        head_idx = HEADER_ROWS.get(name, 1)
        all_vals = _ws(name).get_all_values()
        if len(all_vals) < head_idx:
            return []
        headers = all_vals[head_idx - 1]
        
        # Determine actual number of columns to ignore trailing blank columns
        num_cols = len(headers)
        for i, h in enumerate(headers):
            if not str(h).strip():
                num_cols = i
                break
        headers = headers[:num_cols]
        
        cached = []
        for row in all_vals[head_idx:]:
            if not row or not any(row): continue
            padded_row = row + [""] * (num_cols - len(row))
            cached.append(dict(zip(headers, padded_row[:num_cols])))
            
        sheets_cache.set(name, cached)
    return cached


def _invalidate(name):
    sheets_cache.invalidate(name)


# ─────────────────── RECEIVE TSC ───────────────────
async def receive_tsc(data: dict) -> str:
    try:
        tsc_no = data.get("tsc_no", "").strip()
        received_from = data.get("received_from", "").strip()
        received_date = data.get("received_date", "") or _today_str()
        pl_no = data.get("pl_no", "")
        oh_type = data.get("oh_type", "Overhauling")
        letter_no = data.get("letter_no", "")
        remarks = data.get("remarks", "")

        if not tsc_no:
            return "❌ TSC No is required"

        # Add to receive register
        ws_recv = _ws("TSC_RECEIVE")
        all_recv = _all("TSC_RECEIVE")
        sr_no = len(all_recv) + 1
        fy = _get_fy(_parse_date(received_date))
        ws_recv.append_row([sr_no, tsc_no, received_from, received_date, pl_no, oh_type, letter_no, "", "", remarks, fy])
        _invalidate("TSC_RECEIVE")

        # Update or create in tsc_master
        ws_master = _ws("TSC_MASTER")
        all_master = _all("TSC_MASTER")
        found_row = None
        for idx, rec in enumerate(all_master, start=2):
            if str(rec.get("TSC_No", "")).strip() == tsc_no:
                found_row = idx
                break

        if found_row:
            ws_master.batch_update([
                {"range": f"B{found_row}", "values": [["AVAILABLE"]]},
                {"range": f"M{found_row}", "values": [["FROM_BLW"]]}, # Source Type
                {"range": f"P{found_row}", "values": [[received_from]]},
                {"range": f"Q{found_row}", "values": [[received_date]]},
                {"range": f"R{found_row}", "values": [[letter_no]]},
                {"range": f"N{found_row}", "values": [[pl_no]]},
                {"range": f"O{found_row}", "values": [[oh_type]]},
                {"range": f"S{found_row}", "values": [[remarks]]},
            ])
        else:
            ws_master.append_row([
                tsc_no, "AVAILABLE", "", "", "", "", "",
                "", "", "", "", "", "FROM_BLW",
                pl_no, oh_type, received_from, received_date, letter_no, remarks
            ])
        _invalidate("TSC_MASTER")

        return f"✅ TSC Received Successfully\n📌 TSC: {tsc_no}\n📥 From: {received_from}\n📅 Date: {received_date}\n📄 Letter: {letter_no or '-'}\nStatus: AVAILABLE"
    except Exception as e:
        logger.error(f"Error receiving TSC: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


# ─────────────────── ISSUE (FIT) TSC ───────────────────
async def issue_tsc(data: dict) -> str:
    try:
        tsc_no = data.get("tsc_no", "").strip()
        loco_no = data.get("loco_no", "").strip()
        issue_date = data.get("issue_date", "") or _today_str()
        cause = data.get("cause_of_change", "")
        remarks = data.get("remarks", "")

        if not tsc_no or not loco_no:
            return "❌ TSC No and Loco No are required"

        loco_type = config.detect_diesel_loco_type(loco_no)
        if not loco_type:
            return f"❌ Cannot detect loco type for {loco_no}. Must start with 40/20 (WDP4) or 70/12 (WDG4)"

        working_life = config.get_tsc_working_life(loco_type)

        # Check if loco already has a TSC
        all_master = _all("TSC_MASTER")
        for rec in all_master:
            if str(rec.get("Current_Loco", "")).strip() == loco_no and str(rec.get("Current_Status", "")) == "IN_SERVICE":
                return f"❌ Loco {loco_no} already has TSC {rec.get('TSC_No')} fitted. Remove it first."

        # Find TSC in master
        ws_master = _ws("TSC_MASTER")
        found_row = None
        existing_doc = ""
        for idx, rec in enumerate(all_master, start=2):
            if str(rec.get("TSC_No", "")).strip() == tsc_no:
                found_row = idx
                existing_doc = str(rec.get("DOC", "")).strip()
                break

        if not found_row:
            return f"❌ TSC {tsc_no} not found. Receive it first."

        # DOC logic: set on first fit after OH, keep unchanged on re-fit
        is_new_doc = False
        doc = existing_doc
        if not doc:
            doc = issue_date
            is_new_doc = True

        # Update master
        ws_master.batch_update([
            {"range": f"B{found_row}", "values": [["IN_SERVICE"]]},
            {"range": f"C{found_row}", "values": [[loco_no]]},
            {"range": f"D{found_row}", "values": [[loco_type]]},
            {"range": f"E{found_row}", "values": [[doc]]},
            {"range": f"F{found_row}", "values": [[""]]},  # age recalculated dynamically
            {"range": f"G{found_row}", "values": [[working_life]]},
            {"range": f"H{found_row}", "values": [[issue_date]]},
            {"range": f"I{found_row}", "values": [[loco_no]]},
        ])
        _invalidate("TSC_MASTER")

        # Add to issue register
        ws_issue = _ws("TSC_ISSUE")
        all_issue = _all("TSC_ISSUE")
        sr_no = len(all_issue) + 1
        fy = _get_fy(_parse_date(issue_date))
        ws_issue.append_row([sr_no, tsc_no, issue_date, loco_no, loco_type, doc,
                             "YES" if is_new_doc else "NO", cause, remarks, fy])
        _invalidate("TSC_ISSUE")

        # Update receive register issue details (find the most recent unmatched receive for this TSC)
        all_recv = _all("TSC_RECEIVE")
        recv_match = None
        # Search backwards to find the latest
        for idx in range(len(all_recv) - 1, -1, -1):
            r = all_recv[idx]
            if str(r.get("T.S.C. No.", "")).strip() == tsc_no and not str(r.get("Date of given on Loco", "")).strip():
                recv_match = idx + 9 # +9 for head=8 (row 8 headers, idx 0 is row 9)
                break
        
        if recv_match:
            ws_recv = _ws("TSC_RECEIVE")
            ws_recv.batch_update([
                {"range": f"H{recv_match}", "values": [[issue_date]]},
                {"range": f"I{recv_match}", "values": [[loco_no]]},
                {"range": f"J{recv_match}", "values": [[remarks]]},
            ])
            _invalidate("TSC_RECEIVE")

        # Update loco running
        await _update_loco_running(tsc_no, loco_no, loco_type, issue_date, doc, working_life)

        doc_note = " (NEW DOC set)" if is_new_doc else " (DOC unchanged)"
        return (f"✅ TSC Fitted Successfully\n📌 TSC: {tsc_no}\n🚂 Loco: {loco_no} ({loco_type})\n"
                f"📅 Fitment: {issue_date}\n📅 DOC: {doc}{doc_note}\n⏳ Working Life: {working_life} years")
    except Exception as e:
        logger.error(f"Error issuing TSC: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


async def _update_loco_running(tsc_no, loco_no, loco_type, fitment_date, doc, working_life):
    ws_run = _ws("TSC_LOCO_RUNNING")
    all_run = _all("TSC_LOCO_RUNNING")

    doc_dt = _parse_date(doc)
    fit_dt = _parse_date(fitment_date)
    now = datetime.now()

    age_days = (now - doc_dt).days if doc_dt else 0
    life_days = working_life * 365
    remaining = life_days - age_days

    if remaining < 0:
        color = "OVERDUE"
    elif remaining < config.TSC_ALERT_CRITICAL_DAYS:
        color = "RED"
    elif remaining < config.TSC_ALERT_WARNING_DAYS:
        color = "YELLOW"
    else:
        color = "GREEN"

    warranty_expiry = (fit_dt + timedelta(days=config.TSC_WARRANTY_YEARS * 365)).strftime(DATE_FMT) if fit_dt else ""
    is_warranty = "YES" if fit_dt and (now - fit_dt).days < config.TSC_WARRANTY_YEARS * 365 else "NO"

    # Check if loco already has entry
    found_row = None
    for idx, rec in enumerate(all_run, start=2):
        if str(rec.get("Loco_No", "")).strip() == loco_no:
            found_row = idx
            break

    row_data = [loco_no, loco_type, tsc_no, fitment_date, doc, age_days,
                working_life, remaining, color, warranty_expiry, is_warranty]

    if found_row:
        cell_range = f"A{found_row}:K{found_row}"
        ws_run.update(cell_range, [row_data])
    else:
        ws_run.append_row(row_data)
    _invalidate("TSC_LOCO_RUNNING")


# ─────────────────── REMOVE TSC ───────────────────
async def remove_tsc(data: dict) -> str:
    try:
        tsc_no = data.get("tsc_no", "").strip()
        removal_date = data.get("removal_date", "") or _today_str()
        cause = data.get("cause", "")
        condition = data.get("condition", "FAILED").upper()  # GOOD / FAILED / OVERDUE
        remarks = data.get("remarks", "")

        if not tsc_no:
            return "❌ TSC No is required"

        ws_master = _ws("TSC_MASTER")
        all_master = _all("TSC_MASTER")

        found_row = None
        rec_data = None
        for idx, rec in enumerate(all_master, start=2):
            if str(rec.get("TSC_No", "")).strip() == tsc_no:
                found_row = idx
                rec_data = rec
                break

        if not found_row:
            return f"❌ TSC {tsc_no} not found"

        from_loco = str(rec_data.get("Current_Loco", "")).strip()
        loco_type = str(rec_data.get("Loco_Type", "")).strip()
        fitment_date_str = str(rec_data.get("Last_Fitment_Date", "")).strip()
        doc_str = str(rec_data.get("DOC", "")).strip()
        working_life = int(rec_data.get("Working_Life_Years", 6) or 6)

        # Calculate age at removal
        doc_dt = _parse_date(doc_str)
        removal_dt = _parse_date(removal_date)
        age_years = round((removal_dt - doc_dt).days / 365, 2) if doc_dt and removal_dt else 0

        # Warranty check
        fit_dt = _parse_date(fitment_date_str)
        is_warranty = False
        if fit_dt and removal_dt:
            is_warranty = (removal_dt - fit_dt).days <= config.TSC_WARRANTY_YEARS * 365

        pl_no = config.TSC_PL_NUMBERS["WARRANTY"] if is_warranty else config.TSC_PL_NUMBERS["OVERHAULING"]
        oh_type = "Warranty" if is_warranty else "Overhauling"

        # Next Action logic
        user_next_action = data.get("next_action", "").upper() # SEND_TO_BLW or KEEP_FOR_FITMENT
        if not user_next_action:
            user_next_action = "KEEP_FOR_FITMENT" if condition == "GOOD" else "SEND_TO_BLW"

        new_status = "AVAILABLE" if user_next_action == "KEEP_FOR_FITMENT" else "WAITING_FOR_DISPATCH"
        source_type = "OLD_REMOVED" if user_next_action == "KEEP_FOR_FITMENT" else ""

        # Update master
        ws_master.batch_update([
            {"range": f"B{found_row}", "values": [[new_status]]},
            {"range": f"C{found_row}", "values": [[""]]},  # clear current loco
            {"range": f"J{found_row}", "values": [[removal_date]]},
            {"range": f"K{found_row}", "values": [[cause]]},
            {"range": f"L{found_row}", "values": [["YES" if is_warranty else "NO"]]},
            {"range": f"M{found_row}", "values": [[source_type]]},
            {"range": f"N{found_row}", "values": [[pl_no]]},
            {"range": f"O{found_row}", "values": [[oh_type]]},
        ])
        _invalidate("TSC_MASTER")

        # If waiting for dispatch, add to buffer sheet
        if new_status == "WAITING_FOR_DISPATCH":
            ws_wait = _ws("TSC_WAITING_DISPATCH")
            all_wait = _all("TSC_WAITING_DISPATCH")
            # Sr. No., Turbo No., Removed from loco no., Removed date, Fitment date, commissioning date, Reason to remove
            ws_wait.append_row([len(all_wait)+1, tsc_no, from_loco, removal_date, fitment_date_str, doc_str, cause, remarks])
            _invalidate("TSC_WAITING_DISPATCH")

        # Add to removal register
        ws_rem = _ws("TSC_REMOVAL")
        all_rem = _all("TSC_REMOVAL")
        sr_no = len(all_rem) + 1
        fy = _get_fy(removal_dt)
        ws_rem.append_row([sr_no, tsc_no, removal_date, from_loco, cause, condition,
                           next_action, "YES" if is_warranty else "NO", remarks, fy])
        _invalidate("TSC_REMOVAL")

        # Remove from loco running
        await _remove_from_loco_running(from_loco)

        # Log premature failure
        pf_msg = ""
        if is_premature:
            ws_pf = _ws("TSC_PREMATURE_FAILURE")
            all_pf = _all("TSC_PREMATURE_FAILURE")
            pf_sr = len(all_pf) + 1
            ws_pf.append_row([pf_sr, tsc_no, from_loco, loco_type, fitment_date_str, doc_str,
                              removal_date, age_years, working_life, cause, "YES" if is_warranty else "NO",
                              pl_no, next_action, fy, remarks])
            _invalidate("TSC_PREMATURE_FAILURE")
            pf_msg = f"\n⚠️ PREMATURE FAILURE — Age: {age_years}yr / Life: {working_life}yr"

        warranty_msg = "\n🔵 WARRANTY CASE" if is_warranty else ""

        return (f"✅ TSC Removed\n📌 TSC: {tsc_no}\n🚂 From Loco: {from_loco}\n📅 Removed: {removal_date}\n"
                f"📋 Cause: {cause}\n🔧 Condition: {condition}\n➡️ Next: {next_action}\n"
                f"⏳ Age: {age_years} years{warranty_msg}{pf_msg}")
    except Exception as e:
        logger.error(f"Error removing TSC: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


async def _remove_from_loco_running(loco_no):
    if not loco_no:
        return
    ws_run = _ws("TSC_LOCO_RUNNING")
    all_run = _all("TSC_LOCO_RUNNING")
    for idx, rec in enumerate(all_run, start=2):
        if str(rec.get("Loco_No", "")).strip() == loco_no:
            ws_run.delete_rows(idx)
            _invalidate("TSC_LOCO_RUNNING")
            return


# ─────────────────── SEND TO BLW ───────────────────
async def send_to_blw(data: dict) -> str:
    try:
        tsc_no = data.get("tsc_no", "").strip()
        dispatch_date = data.get("dispatch_date", "") or _today_str()
        pl_no = data.get("pl_no", "")
        oh_type = data.get("oh_type", "Overhauling")
        letter_no = data.get("dispatch_letter_no", "")
        warranty_no = data.get("warranty_no", "")
        remarks = data.get("remarks", "")

        if not tsc_no:
            return "❌ TSC No is required"

        # Update master status
        ws_master = _ws("TSC_MASTER")
        all_master = _all("TSC_MASTER")
        found_row = None
        master_rec = None
        for idx, rec in enumerate(all_master, start=2):
            if str(rec.get("TSC_No", "")).strip() == tsc_no:
                found_row = idx
                master_rec = rec
                break

        if found_row:
            ws_master.batch_update([
                {"range": f"B{found_row}", "values": [["SENT_TO_BLW"]]},
                {"range": f"M{found_row}", "values": [[""]]}, # Clear source type
            ])
        _invalidate("TSC_MASTER")
        
        # Remove from waiting buffer if present
        if master_rec and str(master_rec.get("Current_Status", "")) == "WAITING_FOR_DISPATCH":
            ws_wait = _ws("TSC_WAITING_DISPATCH")
            all_wait = _all("TSC_WAITING_DISPATCH")
            for i, r in enumerate(all_wait, start=2):
                if str(r.get("Turbo No.", "")).strip() == tsc_no:
                    ws_wait.delete_rows(i)
                    break
            _invalidate("TSC_WAITING_DISPATCH")
        doc = str(master_rec.get("DOC", "")) if master_rec else ""
        fit_date = str(master_rec.get("Last_Fitment_Date", "")) if master_rec else ""
        rem_date = str(master_rec.get("Last_Removal_Date", "")) if master_rec else ""
        rem_cause = str(master_rec.get("Last_Removal_Cause", "")) if master_rec else ""

        # Add to dispatch register
        ws_disp = _ws("TSC_BLW_DISPATCH")
        all_disp = _all("TSC_BLW_DISPATCH")
        sr_no = len(all_disp) + 1
        fy = _get_fy(_parse_date(dispatch_date))
        ws_disp.append_row([sr_no, tsc_no, from_loco, rem_date, fit_date, doc, rem_cause,
                            warranty_no or letter_no, letter_no, dispatch_date, fy, "PENDING"])
        _invalidate("TSC_BLW_DISPATCH")

        return (f"✅ TSC Sent to BLW\n📌 TSC: {tsc_no}\n📅 Dispatch: {dispatch_date}\n"
                f"📄 Letter: {letter_no or '-'}\n🔧 Type: {oh_type}")
    except Exception as e:
        logger.error(f"Error sending to BLW: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


# ─────────────────── QUERY FUNCTIONS ───────────────────
async def get_dashboard_stats() -> dict:
    try:
        all_master = _all("TSC_MASTER")
        all_disp = _all("TSC_BLW_DISPATCH")
        all_recv = _all("TSC_RECEIVE")
        all_pf = _all("TSC_PREMATURE_FAILURE")
        all_run = _all("TSC_LOCO_RUNNING")

        in_service = sum(1 for r in all_master if str(r.get("Current_Status", "")) == "IN_SERVICE")
        available = sum(1 for r in all_master if str(r.get("Current_Status", "")) == "AVAILABLE")
        waiting_disp = sum(1 for r in all_master if str(r.get("Current_Status", "")) == "WAITING_FOR_DISPATCH")
        sent_blw = sum(1 for r in all_master if str(r.get("Current_Status", "")) == "SENT_TO_BLW")
        total = in_service + available + waiting_disp

        total_sent = len(all_disp)
        total_received = len(all_recv)
        at_blw = (total_sent - total_received) + 18
        if at_blw < 0: at_blw = 0

        warranty_cases = sum(1 for r in all_master if str(r.get("Is_Warranty", "")).upper() == "YES"
                             and str(r.get("Current_Status", "")) != "IN_SERVICE")
        premature_count = len(all_pf)

        # Overdue count from running
        overdue = sum(1 for r in all_run if str(r.get("Status_Color", "")) == "OVERDUE")
        critical = sum(1 for r in all_run if str(r.get("Status_Color", "")) == "RED")

        return {
            "total": total, "in_service": in_service, "available": available,
            "waiting_dispatch": waiting_disp, "at_blw": at_blw,
            "total_sent_blw": total_sent, "total_received_blw": total_received,
            "warranty_cases": warranty_cases, "premature_failures": premature_count,
            "overdue": overdue, "critical": critical,
        }
    except Exception as e:
        logger.error(f"Error getting TSC stats: {e}", exc_info=True)
        return {"error": str(e)}


async def get_running_tscs() -> list:
    try:
        all_run = _all("TSC_LOCO_RUNNING")
        # Recalculate ages dynamically
        result = []
        for rec in all_run:
            doc_dt = _parse_date(rec.get("DOC", ""))
            fit_dt = _parse_date(rec.get("Fitment_Date", ""))
            now = datetime.now()
            wl = int(rec.get("Working_Life_Years", 6) or 6)

            age_days = (now - doc_dt).days if doc_dt else 0
            remaining = (wl * 365) - age_days
            age_years = round(age_days / 365, 1)

            if remaining < 0:
                color = "OVERDUE"
            elif remaining < config.TSC_ALERT_CRITICAL_DAYS:
                color = "RED"
            elif remaining < config.TSC_ALERT_WARNING_DAYS:
                color = "YELLOW"
            else:
                color = "GREEN"

            is_warranty = "YES"
            if fit_dt and (now - fit_dt).days >= config.TSC_WARRANTY_YEARS * 365:
                is_warranty = "NO"

            result.append({
                "loco_no": rec.get("Loco_No", ""),
                "loco_type": rec.get("Loco_Type", ""),
                "tsc_no": rec.get("TSC_No", ""),
                "fitment_date": rec.get("Fitment_Date", ""),
                "doc": rec.get("DOC", ""),
                "age_days": age_days,
                "age_years": age_years,
                "working_life": wl,
                "remaining_days": remaining,
                "status_color": color,
                "is_warranty": is_warranty,
            })
        result.sort(key=lambda x: x.get("remaining_days", 9999))
        return result
    except Exception as e:
        logger.error(f"Error getting running TSCs: {e}", exc_info=True)
        return []


async def get_available_tscs() -> list:
    try:
        all_master = _all("TSC_MASTER")
        res = []
        for r in all_master:
            if str(r.get("Current_Status", "")) == "AVAILABLE":
                source_val = str(r.get("Blank", "")).strip()
                source = "OLD REMOVED" if source_val == "OLD_REMOVED" else "FROM BLW"
                doc = r.get("DOC", "")
                fit_date = r.get("Last_Fitment_Date", "")
                rem_date = r.get("Last_Removal_Date", "")
                loco_no = r.get("Last_Fitment_Loco", "")
                
                age_used = ""
                if source == "OLD REMOVED" and fit_date and rem_date:
                    f_dt = _parse_date(fit_date)
                    r_dt = _parse_date(rem_date)
                    if f_dt and r_dt:
                        age_used = f"{round((r_dt - f_dt).days / 365, 2)} yr"

                res.append({
                    "tsc_no": r.get("TSC_No", ""),
                    "source": source,
                    "received_date": r.get("Last_Received_Date", "") or rem_date,
                    "oh_type": r.get("OH_Type", ""),
                    "doc": doc,
                    "age_used": age_used,
                    "removed_from": loco_no,
                    "remarks": r.get("Remarks", "")
                })
        return res
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return []


async def get_blw_account() -> dict:
    try:
        all_disp = _all("TSC_BLW_DISPATCH")
        all_recv = _all("TSC_RECEIVE")
        sent = len(all_disp)
        received = len(all_recv)
        pending_list = [
            {"tsc_no": r.get("T.S.C. No.", ""), "dispatch_date": r.get("DATE OF SEND TO BLW", ""),
             "oh_type": "Warranty" if str(r.get("LETTER NO. /WARRANTY NO.", "")).startswith("W-") else "Overhauling"}
            for r in all_disp if str(r.get("Status", "")) == "PENDING"
        ]
        return {"total_sent": sent, "total_received": received,
                "balance_at_blw": max(0, sent - received), "pending": pending_list}
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return {"error": str(e)}


async def get_tsc_history(tsc_no: str) -> dict:
    try:
        all_master = _all("TSC_MASTER")
        master = None
        for r in all_master:
            if str(r.get("TSC_No", "")).strip() == tsc_no.strip():
                master = r
                break
        if not master:
            return {"error": f"TSC {tsc_no} not found"}

        all_issue = _all("TSC_ISSUE")
        issues = [r for r in all_issue if str(r.get("TSC_No", "")).strip() == tsc_no.strip()]

        all_rem = _all("TSC_REMOVAL")
        removals = [r for r in all_rem if str(r.get("TSC_No", "")).strip() == tsc_no.strip()]

        return {"master": master, "issues": issues, "removals": removals}
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return {"error": str(e)}


async def get_loco_tsc_history(loco_no: str) -> dict:
    try:
        all_issue = _all("TSC_ISSUE")
        all_rem = _all("TSC_REMOVAL")

        issues = [r for r in all_issue if str(r.get("Loco_No", "")).strip() == loco_no.strip()]
        removals = [r for r in all_rem if str(r.get("From_Loco", "")).strip() == loco_no.strip()]

        # Current TSC
        all_run = _all("TSC_LOCO_RUNNING")
        current = None
        for r in all_run:
            if str(r.get("Loco_No", "")).strip() == loco_no.strip():
                current = r
                break

        loco_type = config.detect_diesel_loco_type(loco_no)
        return {"loco_no": loco_no, "loco_type": loco_type,
                "current_tsc": current, "fit_history": issues, "removal_history": removals}
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return {"error": str(e)}


async def get_premature_failures() -> list:
    try:
        return _all("TSC_PREMATURE_FAILURE")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return []

async def get_waiting_dispatch() -> list:
    try:
        return _all("TSC_WAITING_DISPATCH")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return []


async def get_register(register_name: str, fy: str = None) -> dict:
    try:
        key_map = {
            "receive": "TSC_RECEIVE", "issue": "TSC_ISSUE",
            "removal": "TSC_REMOVAL", "blw_dispatch": "TSC_BLW_DISPATCH",
            "waiting": "TSC_WAITING_DISPATCH"
        }
        key = key_map.get(register_name)
        if not key:
            return {"data": []}
        data = _all(key)
        
        # Calculate summary if needed
        summary = []
        if register_name in ("receive", "blw_dispatch"):
            fy_counts = {}
            for r in data:
                r_fy = standardize_fy(str(r.get("Session", r.get("FY_Session", ""))))
                if not r_fy: continue
                
                if register_name == "receive":
                    oh_type = str(r.get("AGAINST WARRANTY /OVER HAULING", "")).strip()
                else:
                    letter = str(r.get("LETTER NO. /WARRANTY NO.", "")).strip()
                    oh_type = "Warranty" if "W-" in letter else "Overhauling"
                
                if r_fy not in fy_counts:
                    fy_counts[r_fy] = {"Warranty": 0, "Overhauling": 0}
                if "WARRANTY" in oh_type.upper():
                    fy_counts[r_fy]["Warranty"] += 1
                else:
                    fy_counts[r_fy]["Overhauling"] += 1
            
            for f, counts in sorted(fy_counts.items(), reverse=True):
                if fy and f != fy: continue
                summary.append({"fy": f, "warranty": counts["Warranty"], "overhaul": counts["Overhauling"]})

        if fy:
            target_fy = standardize_fy(fy)
            filtered_data = []
            for r in data:
                # Try specific columns, then try to derive from dates
                r_fy = standardize_fy(str(r.get("Session", r.get("FY_Session", r.get("Session", "")))))
                if not r_fy:
                    # Try deriving from "Removed date" or "Removal Date"
                    dt_str = r.get("Removed date") or r.get("Removal Date") or r.get("Issue_Date") or r.get("Last_Received_Date")
                    if dt_str:
                        r_fy = _get_fy(_parse_date(str(dt_str)))
                
                if r_fy == target_fy:
                    filtered_data.append(r)
            data = filtered_data
            
        return {"data": data, "summary": summary}
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return {"data": []}


async def get_alerts() -> list:
    alerts = []
    try:
        running = await get_running_tscs()
        for r in running:
            rem = r.get("remaining_days", 9999)
            if r["status_color"] == "OVERDUE":
                alerts.append({"type": "OVERDUE", "severity": "critical",
                    "msg": f"Loco {r['loco_no']}: TSC {r['tsc_no']} — OVERDUE by {abs(rem)} days"})
            elif r["status_color"] == "RED":
                alerts.append({"type": "CRITICAL", "severity": "warning",
                    "msg": f"Loco {r['loco_no']}: TSC {r['tsc_no']} — {rem} days remaining"})
            elif r["status_color"] == "YELLOW":
                alerts.append({"type": "WARNING", "severity": "info",
                    "msg": f"Loco {r['loco_no']}: TSC {r['tsc_no']} — {rem} days remaining"})

        blw = await get_blw_account()
        if blw.get("balance_at_blw", 0) > 0:
            alerts.append({"type": "BLW_PENDING", "severity": "info",
                "msg": f"{blw['balance_at_blw']} TSC(s) pending at BLW"})
    except Exception as e:
        logger.error(f"Error getting alerts: {e}", exc_info=True)
    return alerts
