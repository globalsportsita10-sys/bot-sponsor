import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
TOKEN = "8601357271:AAEmVAdioTlrZ5nMAwZgOwM7U-ggmp_flL4"
ADMIN_ID = 8361466889

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATI ---
CANALI_STREAMING = [f"Streaming {i}" for i in range(1, 10)]
CANALI_FISSI = ["Goal", "Juventus Planet"]
TUTTI_I_CANALI = CANALI_FISSI + CANALI_STREAMING
PREZZI_INC = {"1K": 50, "2K": 80, "3K": 120, "5K": 200}

def calcola_prezzo(sel, ore):
    tot = 0
    p_fissi = {"Goal": {3: 5, 6: 7.5, 12: 11, 24: 13.5}, "Juventus Planet": {3: 4, 6: 5.5, 12: 8, 24: 12}}
    for c in CANALI_FISSI:
        if c in sel: tot += p_fissi[c].get(ore, 0)
    str_sel = [c for c in sel if "Streaming" in c]
    q = len(str_sel)
    if q > 0:
        if q == 9: p_s = {3: 25, 6: 35, 12: 50, 24: 65}
        elif 5 <= q <= 8: p_s = {3: 20, 6: 30, 12: 40, 24: 50}
        elif 3 <= q <= 4: p_s = {3: 15, 6: 20, 12: 35, 24: 45}
        else: p_s = {3: 6*q, 6: 9.5*q, 12: 15*q, 24: 19.5*q}
        tot += p_s.get(ore, 0)
    return tot

# --- TASTIERE ---
def kb_selezione(sel):
    kb = []
    # Goal e Juve sulla stessa riga
    row_fissi = []
    for c in CANALI_FISSI:
        s = " ✅" if c in sel else ""
        row_fissi.append(InlineKeyboardButton(f"{c}{s}", callback_data=f"t_{c}"))
    kb.append(row_fissi)

    # Streaming 3 per riga
    row = []
    for c in CANALI_STREAMING:
        s = "✅" if c in sel else c.split()[1]
        row.append(InlineKeyboardButton(f"Str {s}", callback_data=f"t_{c}"))
        if len(row) == 3: kb.append(row); row = []

    kb.append([InlineKeyboardButton("✨ Seleziona Tutti", callback_data="all_in")])
    kb.append([InlineKeyboardButton("➡️ AVANTI", callback_data="go_durata")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")])
    return InlineKeyboardMarkup(kb)

# --- SERVER ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Online"
def run(): webapp.run(host='0.0.0.0', port=10000)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_id = update.effective_user.id
    context.user_data.clear()
    if u_id == ADMIN_ID:
        kb = [[InlineKeyboardButton("📊 Ordini", callback_data='admin_orders')], [InlineKeyboardButton("🌐 Vista Utente", callback_data='user_view')]]
        await (update.callback_query.edit_message_text("👮‍♂️ ADMIN", reply_markup=InlineKeyboardMarkup(kb)) if update.callback_query else update.message.reply_text("👮‍♂️ ADMIN", reply_markup=InlineKeyboardMarkup(kb)))
    else:
        kb = [[InlineKeyboardButton("📢 Sponsor Standard", callback_data='sel_std')], [InlineKeyboardButton("🚀 Incrementi", callback_data='menu_inc')]]
        await (update.callback_query.edit_message_text("👋 Benvenuto!", reply_markup=InlineKeyboardMarkup(kb)) if update.callback_query else update.message.reply_text("👋 Benvenuto!", reply_markup=InlineKeyboardMarkup(kb)))

async def gestore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    u_data = context.user_data
    await query.answer()

    if data in ['sel_std', 'user_view']:
        u_data['sel'] = []
        await query.edit_message_text("Seleziona i canali:", reply_markup=kb_selezione(u_data['sel']))

    elif data.startswith('t_'):
        c = data.replace('t_', '')
        if c in u_data['sel']: u_data['sel'].remove(c)
        else: u_data['sel'].append(c)
        await query.edit_message_reply_markup(reply_markup=kb_selezione(u_data['sel']))

    elif data == 'all_in':
        u_data['sel'] = list(TUTTI_I_CANALI)
        await query.edit_message_reply_markup(reply_markup=kb_selezione(u_data['sel']))

    elif data == 'go_durata':
        if not u_data.get('sel'):
            return await query.answer("⚠️ Devi selezionare almeno un canale per poter proseguire!", show_alert=True)
        kb = [[InlineKeyboardButton("3h", callback_data="h_3"), InlineKeyboardButton("6h", callback_data="h_6")],
              [InlineKeyboardButton("12h", callback_data="h_12"), InlineKeyboardButton("24h", callback_data="h_24")],
              [InlineKeyboardButton("⬅️ Indietro", callback_data="sel_std")]]
        await query.edit_message_text("Scegli la durata:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith('h_'):
        u_data['ore'] = int(data.replace('h_', ''))
        u_data['prezzo'] = calcola_prezzo(u_data['sel'], u_data['ore'])
        kb = []
        for i in range(1, 6):
            g = (datetime.now() + timedelta(days=i)).strftime("%d/%m")
            kb.append([InlineKeyboardButton(f"🟢 {g}", callback_data=f"d_{g}")])
        await query.edit_message_text("Seleziona il giorno:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith('d_'):
        u_data['data'] = data.replace('d_', '')
        kb = [[InlineKeyboardButton("🌅 Mattina (09-12)", callback_data="f_09-12")],
              [InlineKeyboardButton("☀️ Pomeriggio (15-18)", callback_data="f_15-18")],
              [InlineKeyboardButton("🌙 Sera (21-00)", callback_data="f_21-00")]]
        await query.edit_message_text(f"Giorno: {u_data['data']}\nScegli l'orario:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith('f_'):
        u_data['fascia'] = data.replace('f_', '')
        txt = f"✅ RIEPILOGO\nCanali: {len(u_data['sel'])}\nData: {u_data['data']} ({u_data['fascia']})\n💰 Totale: {u_data['prezzo']}€"
        kb = [[InlineKeyboardButton("✅ INVIA", callback_data="conf")], [InlineKeyboardButton("⬅️ Indietro", callback_data="sel_std")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "conf":
        await context.bot.send_message(ADMIN_ID, f"💰 ORDINE @{query.from_user.username}\n{u_data}")
        await query.edit_message_text("✅ Inviato! Ti contatteremo per il pagamento.")

    elif data == 'back_to_start': await start(update, context)

if __name__ == '__main__':
    Thread(target=run).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(CallbackQueryHandler(gestore))
    bot.run_polling()
