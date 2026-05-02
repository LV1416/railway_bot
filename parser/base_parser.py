import re

def _norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[\s\.\-_\/]+", " ", s)
    return s

def parse_key_values(text: str) -> dict:
    """
    Parse a free-form message into key/value pairs.
    """
    fields: dict[str, str] = {}
    if not text:
        return fields

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if _norm_key(line) in {"dga report", "panto status"}:
            continue

        m = re.match(r"^\s*([^:=\-]{1,60}?)\s*(?:-|:|=)\s*(.*?)\s*$", line)
        if not m:
            continue

        key = _norm_key(m.group(1))
        value = (m.group(2) or "").strip()
        if key:
            fields[key] = value

    return fields

def extract_free_text_fields(text: str) -> dict[str, str]:
    t = (text or "").strip()
    if not t:
        return {}

    tn = _norm_key(t)
    out: dict[str, str] = {}

    m = re.search(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b", t)
    if m:
        dd, mm, yyyy = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        out["date"] = f"{dd}.{mm}.{yyyy}"

    # Removed the dead Devanagari regex match
    m = re.search(r"\bloco\s*(?:no\.?|number)?\s*[:\-]?\s*(\d{3,6})\b", t, re.IGNORECASE)
    if m:
        out["loco no"] = m.group(1)

    m = re.search(r"\b(i)\s*([0-9]{8})\s*([a-z0-9]+)\b", t, re.IGNORECASE)
    if m:
        out["sr no"] = f"{m.group(1).upper()}{m.group(2)} {m.group(3).upper()}"

    m = re.search(r"\bmake\b\s*[:\-]?\s*(BLW|GM)\b", t, re.IGNORECASE)
    if m:
        out["make"] = m.group(1).upper()

    m = re.search(r"\bR\s*-\s*\d+\b|\bR\d+\b", t, re.IGNORECASE)
    if m:
        out["type"] = re.sub(r"\s+", "", m.group(0)).upper()

    if "clutch" in tn:
        out["item"] = "Clutch"
    elif any(k in tn for k in ["turbo", "tsc", "hhp turbo"]):
        out["item"] = "TSC"

    if re.search(r"\b(received|reasived|received from)\b", tn):
        out["status"] = "Received"
    if re.search(r"\b(removed|remove|withdrawn)\b", tn):
        out["status"] = "Removed"
    if re.search(r"\b(fitted|fitment|installed)\b", tn):
        out["status"] = "Fitted"
    if re.search(r"\b(changed|replaced)\b", tn):
        out["status"] = out.get("status") or "Changed"

    m = re.search(r"\b(rea?son|resion)\b\s*[:\-]?\s*(.+)$", t, re.IGNORECASE)
    if m:
        out["reason"] = m.group(2).strip()
    else:
        m = re.search(r"\bengine\s+block\s+change\b", tn)
        if m:
            out["reason"] = "Engine block change"

    return out

_ALIASES: dict[str, list[str]] = {
    # Common
    "date": ["date"],
    "loco no": ["loco no", "loco no.", "loco", "locono"],
    "schedule": ["schedule"],
    "remark": ["remark", "remarks"],
    # Main equipment
    "item": ["item"],
    "side": ["side"],
    "status": ["status"],
    "sr no": ["sr no", "sr. no", "sr. no.", "srno", "s no", "s. no", "s. no.", "sno", "serial no", "serial number"],
    "mfg": ["mfg", "manufacturer"],
    "make": ["make"],
    "type": ["type"],
    "reason": ["reason"],
    "oh date": ["o/h date", "oh date", "overhaul date"],
    "wo no": ["w/o no", "wo no", "work order no", "work order"],
    # DGA report
    "oil": ["oil"],
    "ch4": ["ch4"],
    "c2h4": ["c2h4"],
    "c2h6": ["c2h6"],
    "c2h2": ["c2h2"],
    "h2": ["h2"],
    "co": ["co"],
    "co2": ["co2"],
    "bdv": ["bdv"],
    # Panto status
    "pt1 pressure": ["pt1 pressure", "pt 1 pressure"],
    "pt2 pressure": ["pt2 pressure", "pt 2 pressure"],
    "pt1 ord": ["pt1 ord", "pt 1 ord"],
    "pt2 ord": ["pt2 ord", "pt 2 ord"],
    "pt1 add": ["pt1 add", "pt 1 add"],
    "pt2 add": ["pt2 add", "pt 2 add"],
}

def _get(fields: dict, canonical: str) -> str:
    canonical_n = _norm_key(canonical)
    for alias in _ALIASES.get(canonical_n, [canonical_n]):
        alias_n = _norm_key(alias)
        if alias_n in fields and fields[alias_n] != "":
            return fields[alias_n]
    return ""

def normalize_fields(message_type: str, fields: dict) -> dict:
    mt = (message_type or "").strip().lower()
    if not isinstance(fields, dict):
        return {}

    f: dict[str, str] = {}
    for k, v in fields.items():
        if k is None:
            continue
        ks = _norm_key(str(k))
        if not ks:
            continue
        f[ks] = "" if v is None else str(v).strip()

    def _extract_number(s: str) -> str:
        m = re.search(r"(\d+(?:\.\d+)?)", s or "")
        return m.group(1) if m else ""

    if mt == "panto_status":
        p1_raw = _get(f, "pt1 pressure")
        p2_raw = _get(f, "pt2 pressure")
        if p1_raw:
            f[_norm_key("pt1 pressure")] = _extract_number(p1_raw) or p1_raw
            m = re.search(r"\bheight\b\s*[:\-]?\s*(\d{3,5})\s*mm?\b", p1_raw, re.IGNORECASE)
            if m:
                f[_norm_key("pt1 ord")] = m.group(1)
        if p2_raw:
            f[_norm_key("pt2 pressure")] = _extract_number(p2_raw) or p2_raw
            m = re.search(r"\bheight\b\s*[:\-]?\s*(\d{3,5})\s*mm?\b", p2_raw, re.IGNORECASE)
            if m:
                f[_norm_key("pt2 ord")] = m.group(1)

        if _get(f, "pt1 ord") and _get(f, "pt2 ord"):
            if not _get(f, "pt1 add"):
                f[_norm_key("pt1 add")] = "Active"
            if not _get(f, "pt2 add"):
                f[_norm_key("pt2 add")] = "Active"
        return f

    if mt != "main_equipment":
        return f

    def _format_sr_no(sr_text: str) -> str:
        s = re.sub(r"\s+", " ", (sr_text or "").strip())
        if not s:
            return ""
        m = re.match(r"^(i)\s*([0-9]{8})\s*([a-z0-9]+)?$", s, re.IGNORECASE)
        if m:
            prefix = "I"
            digits = m.group(2)
            suffix = (m.group(3) or "").upper()
            part1, part2, part3 = digits[0:2], digits[2:6], digits[6:8]
            return (f"{prefix} {part1} {part2} {part3}" + (f" {suffix}" if suffix else "")).strip()

        m = re.match(r"^(mod)\s*([0-9]{8})$", s, re.IGNORECASE)
        if m:
            prefix = "MOD"
            digits = m.group(2)
            part1, part2, part3 = digits[0:2], digits[2:4], digits[4:8]
            return f"{prefix} {part1} {part2} {part3}"

        return s

    item_raw = _get(f, "item")
    item_n = _norm_key(item_raw)

    if item_n and any(tok in item_n for tok in ["turbo", "tsc", "hhp"]):
        if "clutch" not in item_n:
            f[_norm_key("item")] = "TSC"

    if "clutch" in item_n:
        f[_norm_key("item")] = "Clutch"

    sr = _get(f, "sr no")
    if sr:
        f[_norm_key("sr no")] = _format_sr_no(sr)

    make = _get(f, "make")
    item_final = _norm_key(_get(f, "item"))
    if ("tsc" in item_final) or ("clutch" in item_final):
        if make.strip().upper() != "BLW":
            f[_norm_key("make")] = "BLW"
    elif (not make) and (("turbo" in item_final) or ("tsc" in item_final) or ("clutch" in item_final)):
        f[_norm_key("make")] = "BLW"

    return f

def infer_message_type(text: str, fields: dict | None = None) -> str:
    text_n = _norm_key(text)
    if "dga report" in text_n:
        return "dga_report"
    if "panto status" in text_n:
        return "panto_status"

    f = fields or parse_key_values(text)
    keys = set(f.keys())

    if any(k in keys for k in {_norm_key("ch4"), _norm_key("c2h2"), _norm_key("bdv"), _norm_key("co2")}):
        return "dga_report"
    if any(k in keys for k in {_norm_key("pt1 pressure"), _norm_key("pt2 pressure"), _norm_key("pt1 ord")}):
        return "panto_status"
    return "main_equipment"

def validate_fields(message_type: str, fields: dict) -> list[str]:
    required_by_type: dict[str, list[str]] = {
        "dga_report": ["date", "loco no", "schedule"],
        "panto_status": ["date", "loco no", "pt1 pressure", "pt2 pressure"],
        "main_equipment": ["date", "loco no", "item", "status"],
    }
    required = required_by_type.get(message_type, [])
    missing: list[str] = []
    for canonical in required:
        if _get(fields, canonical) == "":
            missing.append(canonical)
    return missing
