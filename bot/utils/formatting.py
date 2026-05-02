from datetime import datetime

def format_date(date_str):
    try:
        if not date_str:
            return "-"
        return datetime.strptime(str(date_str), "%Y-%m-%d").strftime("%d-%m-%Y")
    except:
        return str(date_str)

async def build_preview(action_type, data):
    """Build a formatted preview of extracted data."""
    preview = f"📋 **Extracted Information for {action_type}**\n\n"
    preview += f"🔹 **Loco No:** {data.get('loco_no', '-')}\n"
    preview += f"🔹 **Equipment Type:** {data.get('equipment_type', '-')}\n"
    preview += f"🔹 **MFG Serial:** {data.get('serial_no', '-')}\n"
    preview += f"🔹 **LOC Serial:** {data.get('loc_serial', '-')}\n"
    preview += f"🔹 **Make:** {data.get('make', '-')}\n"
    preview += f"🔹 **Mfg Date:** {data.get('mfg_date', '-')}\n"
    preview += f"🔹 **Fitment/Event Date:** {data.get('date', '-')}\n"
    preview += f"🔹 **Schedule:** {data.get('schedule_name', '-')}\n"
    preview += f"🔹 **Last Overhaul Date:** {data.get('last_overhaul_date', '-')}\n"
    preview += f"🔹 **Remarks:** {data.get('remarks', '-')[:100]}\n"
    preview += f"\n✅ **Do you want to proceed with this data?**"
    return preview

async def build_removal_preview(data):
    """Build a formatted preview specifically for equipment removal."""
    preview = f"📋 **Extracted Information for REMOVAL**\n\n"
    preview += f"🔹 **Loco No:** {data.get('loco_no', '-')}\n"
    preview += f"🔹 **Equipment Type:** {data.get('equipment_type', '-')}\n"
    preview += f"🔹 **MFG Serial:** {data.get('serial_no', '-')}\n"
    preview += f"🔹 **Removal Date:** {data.get('date', '-')}\n"
    preview += f"🔹 **Overhaul Type:** {data.get('overhaul_type', '-')}\n"
    preview += f"🔹 **Workshop:** {data.get('workshop', '-')}\n"
    preview += f"🔹 **Remarks:** {data.get('remarks', '-')[:100]}\n"
    preview += f"\n⚠️ **Do you want to confirm this removal?**"
    return preview
