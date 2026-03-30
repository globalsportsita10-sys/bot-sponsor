import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from flask import Flask
from threading import Thread

# --- CONFIGURAZIONE ---
TOKEN = "8601357271:AAEmVAdioTlrZ5nMAwZgOwM7U-ggmp_flL4"
ADMIN_ID = 8361466889

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATI ---
CANALI_STREAMING = [f"Streaming {i}" for i in range(1, 10)]
CANALI_STANDARD_FISSI = ["Goal", "Juventus Planet"]

PREZZI_STD = {
    "Goal": {3: 5, 6: 7.5, 12: 11, 24: 13.5},
    "Juventus Planet": {3: 4, 6: 5.5, 12: 8, 24: 12}
}

def calcola_prezzo_finale(sel, ore):
    totale = 0
    for c in CANALI_STANDARD_FISSI:
        if c in sel:
            totale += PREZZI_STD[c].get(ore, 0)

    str_sel = [c for c in sel if "Streaming" in c]
    q = len(str_sel)
    if q > 0:
        if q == 9: prezzi_str = {3: 25, 6: 35, 12: 50, 24: 65}
        elif 5 <= q <= 8: prezzi_str = {3: 20, 6: 30, 12: 40, 24: 50}
        elif 3 <= q <= 4: prezzi_str = {3: 15, 6: 20, 12: 35, 24: 45}
        else: prezzi_str = {3: 6 * q, 6: 9.5 * q, 12: 15 * q, 24: 19.5 * q}
        totale += prezzi_str.get(ore, 0)
    return totale

# --- TASTIERE ---

def tastiera_selezione_mista(selezionati):
    kb = []
    # Canali fissi (Verticali - 1 per riga)
    for c in CANALI_STANDARD_FISSI:
        s = " ✅" if c in selezionati else ""
        kb.append([InlineKeyboardButton(f"{c}{s}", callback_data=f"t_{c}")])

    kb.append([InlineKeyboardButton("📺 CANALI STREAMING 📺", callback_data="none")])

    # Canali Streaming (Orizzontali - 3 per riga)
    row = []
    for i, c in enumerate(CANALI_STREAMING):
        num = c.split()[1] # Prende solo il numero "1", "2" ecc.
        s = "✅" if c in selezionati else num
        row.append(InlineKeyboardButton(f"Str {s}", callback_data=f"t_{c}"))
        if len(row) == 3:
            kb.append(row)
            row = []

    kb.append([InlineKeyboardButton("✨ SELEZIONA TUTTI STREAMING", callback_data="all_str")])
    kb.append([InlineKeyboardButton("➡️ AVANTI", callback_data="go_durata")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")])
    return InlineKeyboardMarkup(kb)

# --- SERVER WEB ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Online"
def run(): webapp.run(host='0.0.0.0', port=10000)

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_id = update.effective_user.id
    context.user_data.clear()

    if u_id == ADMIN_ID:
        txt = "<b>👮‍♂️ PANNELLO ADMIN</b>"
        kb = [[InlineKeyboardButton("📅 CALENDARIO", callback_data='admin_cal')],
              [InlineKeyboardButton("🌐 VEDI COME UTENTE", callback_data='back_to_start')]]
        reply_markup = InlineKeyboardMarkup(kb)
    else:
        txt = "👋 <b>Benvenuto nello Store!</b>"
        kb = [[InlineKeyboardButton("📢 Sponsor Standard", callback_data='sel_std')],
              [InlineKeyboardButton("🚀 Incrementi", callback_data='menu_incrementi')],
              [InlineKeyboardButton("📋 Listino", url='https://t.me/tuochannel')]]
        reply_markup = InlineKeyboardMarkup(kb)

    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=reply_markup, parse_mode='HTML')

async def gestore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    u_data = context.user_data
    await query.answer()

    if data == 'sel_std':
        u_data['sel'] = u_data.get('sel', [])
        await query.edit_message_text("Seleziona i canali:", reply_markup=tastiera_selezione_mista(u_data['sel']))

    elif data.startswith('t_'):
        c = data.replace('t_', '')
        if c in u_data['sel']: u_data['sel'].remove(c)
        else: u_data['sel'].append(c)
        await query.edit_message_reply_markup(reply_markup=tastiera_selezione_mista(u_data['sel']))

    elif data == 'all_str':
        for c in CANALI_STREAMING:
            if c not in u_data['sel']: u_data['sel'].append(c)
        await query.edit_message_reply_markup(reply_markup=tastiera_selezione_mista(u_data['sel']))

    elif data == 'go_durata':
        if not u_data.get('sel'): return await query.answer("Seleziona almeno un canale!", show_alert=True)
        kb = [[InlineKeyboardButton("3h", callback_data="h_3"), InlineKeyboardButton("6h", callback_data="h_6")],
              [InlineKeyboardButton("12h", callback_data="h_12"), InlineKeyboardButton("24h", callback_data="h_24")],
              [InlineKeyboardButton("⬅️ Indietro", callback_data="sel_std")]]
        await query.edit_message_text("Scegli la durata:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith('h_'):
        ore = int(data.replace('h_', ''))
        u_data['ore'] = ore
        prezzo = calcola_prezzo_finale(u_data['sel'], ore)
        await query.edit_message_text(f"🛒 <b>RIEPILOGO</b>\nCanali: {len(u_data['sel'])}\nTotale: {prezzo}€",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📅 DATA", callback_data="admin_cal")]]),
                                     parse_mode='HTML')

    elif data == 'back_to_start':
        await start(update, context)

if __name__ == '__main__':
    Thread(target=run).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(CallbackQueryHandler(gestore_callback))
    bot.run_polling()
