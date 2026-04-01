import logging, calendar, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
TOKEN = "8601357271:AAEmVAdioTlrZ5nMAwZgOwM7U-ggmp_flL4"
ADMIN_ID = 8361466889

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- I TUOI CANALI REALI ---
CANALI_FISSI = {"Goal": "⚽️ Goal", "Juventus Planet": "🦓 Juventus Planet"}
CANALI_STR = {f"Streaming {i}": f"🖥 Streaming {i}" for i in range(1, 10)}
TUTTI_I_CANALI = {**CANALI_FISSI, **CANALI_STR}

# --- LOGICA PREZZI ---
def calcola_prezzo_totale(u_data):
    sel = u_data.get('sel', [])
    ore = u_data.get('ore', 3)
    tot = 0

    # Prezzi Canali Fissi
    p_fissi = {"Goal": {3: 5, 6: 7.5, 12: 11, 24: 13.5}, "Juventus Planet": {3: 4, 6: 5.5, 12: 8, 24: 12}}
    for c in ["Goal", "Juventus Planet"]:
        if c in sel: tot += p_fissi[c].get(ore, 0)

    # Prezzi Streaming (Scontistica quantità)
    q_str = len([c for c in sel if "Streaming" in c])
    if q_str > 0:
        if q_str == 9: p = {3: 25, 6: 35, 12: 50, 24: 65}
        elif 5 <= q_str <= 8: p = {3: 20, 6: 30, 12: 40, 24: 50}
        elif 3 <= q_str <= 4: p = {3: 15, 6: 20, 12: 35, 24: 45}
        else: p = {3: 6*q_str, 6: 9.5*q_str, 12: 15*q_str, 24: 19.5*q_str}
        tot += p.get(ore, 0)

    # Aggiunte
    if u_data.get('repost'): tot += (3 * len(sel))
    if u_data.get('fissato'): tot += (1 * len(sel))
    return tot

# --- TASTIERE ---
def kb_canali(sel):
    kb = []
    # Fissi
    kb.append([InlineKeyboardButton(f"{'✅ ' if c in sel else ''}{name}", callback_data=f"t_{c}") for c in CANALI_FISSI])
    # Streaming (Griglia)
    row = []
    for c, name in CANALI_STR.items():
        row.append(InlineKeyboardButton(f"{'✅ ' if c in sel else ''}Str {c.split()[-1]}", callback_data=f"t_{c}"))
        if len(row) == 3: kb.append(row); row = []
    kb.append([InlineKeyboardButton("✨ Seleziona Tutti", callback_data="all_in")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back"), InlineKeyboardButton("Avanti ➡️", callback_data="go_durata")])
    return InlineKeyboardMarkup(kb)

# --- SERVER & HANDLERS ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Online"
def run(): webapp.run(host='0.0.0.0', port=10000)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_id = update.effective_user.id
    context.user_data.clear()
    kb = [[InlineKeyboardButton("📣 Acquista Sponsor", callback_data='sel_std')],
          [InlineKeyboardButton("🎁 Stato Ordine", callback_data='status'), InlineKeyboardButton("🆘 Assistenza", url='https://t.me/GlobalSportsContatto')]]
    txt = "👮‍♂️ <b>ADMIN</b>" if u_id == ADMIN_ID else "👋 <b>Benvenuto!</b>"
    if update.callback_query: await update.callback_query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    else: await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = context.user_data
    await q.answer()

    if q.data == 'sel_std':
        u['sel'] = []
        await q.edit_message_text("👇 <b>Seleziona i canali:</b>", reply_markup=kb_canali(u['sel']), parse_mode='HTML')
    elif q.data.startswith('t_'):
        c = q.data.replace('t_', '')
        if c in u['sel']: u['sel'].remove(c)
        else: u['sel'].append(c)
        await q.edit_message_reply_markup(reply_markup=kb_canali(u['sel']))
    elif q.data == 'all_in':
        u['sel'] = list(TUTTI_I_CANALI.keys())
        await q.edit_message_reply_markup(reply_markup=kb_canali(u['sel']))
    elif q.data == 'go_durata':
        if not u.get('sel'): return await q.answer("⚠️ Seleziona almeno un canale!", show_alert=True)
        kb = [[InlineKeyboardButton(f"{h}h", callback_data=f"h_{h}") for h in [3, 6]], [InlineKeyboardButton(f"{h}h", callback_data=f"h_{h}") for h in [12, 24]]]
        await q.edit_message_text("⏱ <b>Scegli la durata:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    elif q.data.startswith('h_'):
        u['ore'] = int(q.data.replace('h_', ''))
        u['repost'] = u['fissato'] = False
        kb = [[InlineKeyboardButton("❌ Repost (+3€)", callback_data="agg_r"), InlineKeyboardButton("❌ Fissato (+1€)", callback_data="agg_f")],
              [InlineKeyboardButton("🗓 Procedi al Calendario", callback_data="go_cal")]]
        await q.edit_message_text("➕ <b>AGGIUNTE</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')
    elif q.data == "go_cal":
        # Qui andrebbe la logica calendario a griglia che abbiamo fatto ieri
        u['data'] = datetime.now().strftime("%d-%m-%Y")
        u['fascia'] = "18:00"
        costo = calcola_prezzo_totale(u)
        canali_txt = ", ".join([TUTTI_I_CANALI[c] for c in u['sel']])
        txt = (f"🛒 <b>IL TUO CARRELLO</b>\n\n🎁 <b>Pacchetto 1</b>\n📢 Canali: {canali_txt}\n🕒 Durata: {u['ore']}h\n💰 <b>Totale: {costo:.2f}€</b>")
        kb = [[InlineKeyboardButton("✅ PROCEDI", callback_data="fin")]]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

if __name__ == '__main__':
    Thread(target=run).start()
    ApplicationBuilder().token(TOKEN).build().add_handler(CommandHandler('start', start)), ApplicationBuilder().token(TOKEN).build().add_handler(CallbackQueryHandler(callback)).run_polling()
