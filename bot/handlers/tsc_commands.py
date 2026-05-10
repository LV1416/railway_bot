from telegram import Update
from telegram.ext import ContextTypes
from bot.services.tsc import get_dashboard_stats, get_running_tscs, get_available_tscs, get_blw_account

async def tsc_summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = await get_dashboard_stats()
    if "error" in stats:
        await update.message.reply_text(f"❌ Error: {stats['error']}")
        return
    
    msg = (
        "📊 *TSC Inventory Summary*\n\n"
        f"🔹 *Total:* {stats.get('total', 0)}\n"
        f"🔹 *In Service:* {stats.get('in_service', 0)}\n"
        f"🔹 *Available:* {stats.get('available', 0)}\n"
        f"🔹 *At BLW:* {stats.get('at_blw', 0)}\n"
        f"🔹 *Waiting Dispatch:* {stats.get('waiting_dispatch', 0)}\n"
        f"🔹 *Warranty Cases:* {stats.get('warranty_cases', 0)}\n"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def tsc_running_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    running = await get_running_tscs()
    if not running:
        await update.message.reply_text("📭 No TSCs currently running on locomotives.")
        return
    
    msg = "🚂 *TSCs Running on Locomotives*\n\n"
    # Limit to top 20 for Telegram msg size
    for r in running[:20]:
        color = "🔴" if r['status_color'] == 'RED' else "🟡" if r['status_color'] == 'YELLOW' else "🟢"
        msg += f"{color} *{r['loco_no']}*: {r['tsc_no']} ({r['remaining_days']} days rem.)\n"
    
    if len(running) > 20:
        msg += f"\n_...and {len(running)-20} more. Check dashboard for full list._"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def tsc_available_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    available = await get_available_tscs()
    if not available:
        await update.message.reply_text("📭 No TSCs available in the shed.")
        return
    
    msg = "📦 *Available TSCs for Fitment*\n\n"
    for r in available[:20]:
        source = "🆕" if r['source'] == 'FROM BLW' else "♻️"
        msg += f"{source} *{r['tsc_no']}* (DOC: {r['doc']})\n"
    
    if len(available) > 20:
        msg += f"\n_...and {len(available)-20} more._"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def tsc_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /tsc_status <loco_no>")
        return
    
    loco_no = context.args[0]
    from bot.services.tsc import get_loco_tsc_history
    res = await get_loco_tsc_history(loco_no)
    
    if "error" in res:
        await update.message.reply_text(f"❌ Error: {res['error']}")
        return

    msg = f"🚂 *Loco {loco_no} TSC Status*\n"
    msg += f"Type: {res.get('loco_type', 'Unknown')}\n\n"

    curr = res.get('current_tsc')
    if curr:
        msg += "✅ *Current Working TSC*\n"
        msg += f"• *No:* {curr['TSC_No']}\n"
        msg += f"• *Fitment:* {curr['Fitment_Date']}\n"
        msg += f"• *DOC:* {curr['DOC']}\n"
        msg += f"• *Status:* {curr.get('Status_Color', 'OK')}\n"
    else:
        msg += "❌ *No TSC currently fitted*\n"

    msg += "\n🕒 *Last Removed TSC*\n"
    rems = res.get('removal_history', [])
    if rems:
        # Sort by date (assuming DD-MM-YYYY, so simple reverse for now as they are appended)
        last = rems[-1]
        msg += f"• *No:* {last.get('TSC_No', 'N/A')}\n"
        msg += f"• *Date:* {last.get('Removal_Date', 'N/A')}\n"
        msg += f"• *Cause:* {last.get('Cause', 'N/A')}\n"
        msg += f"• *Condition:* {last.get('Condition', 'N/A')}\n"
    else:
        msg += "• No removal history found.\n"

    await update.message.reply_text(msg, parse_mode='Markdown')

async def tsc_blw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = await get_dashboard_stats()
    blw = await get_blw_account()
    
    msg = (
        "🏭 *TSC BLW Account*\n\n"
        f"📍 *Currently at BLW:* {stats.get('at_blw', 15)}\n"
        f"📤 *Total Sent:* {blw.get('total_sent', 0)}\n"
        f"📥 *Total Received:* {blw.get('total_received', 0)}\n"
    )
    
    pending = blw.get('pending', [])
    if pending:
        msg += "\n*Pending Repair/OH:*\n"
        for p in pending[:10]:
            msg += f"• {p['tsc_no']} (Sent: {p['date_sent']})\n"
            
    await update.message.reply_text(msg, parse_mode='Markdown')
