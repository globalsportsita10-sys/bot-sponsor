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

# --- DATI E PREZZI ---
CANALI_STREAMING = [f"Streaming {i}" for i in range(1, 10)]
CANALI_STANDARD_FISSI = ["Goal", "Juventus Planet"]
PREZZI_INCREMENTI = {"1K": 50, "2K": 80, "3K": 120, "5K": 200}

def calcola_prezzo_finale(sel, ore):
    totale = 0
    prezzi_fissi = {"Goal": {3: 5, 6: 7.5, 12: 11, 24: 13.5}, "Juventus Planet": {3: 4, 6: 5.5, 12: 8, 24: 12}}
    for c in CANALI_STANDARD_FISSI:
        if c in sel: totale += prezzi_fissi[c].get(ore, 0)
    str_sel = [c for c in sel if "Streaming" in c]
    q = len(str_sel)
    if q > 0:
        if q == 9: p_str = {3: 25, 6: 35, 12: 50, 24: 65}
        elif 5 <= q <= 8: p_str = {3: 20, 6: 30, 12: 40, 24: 50}
        elif 3 <= q <= 4: p_str = {3: 15, 6: 20, 12: 35, 24: 45}
        else: p_str = {3: 6*q, 6: 9.5*q, 12: 15*q, 24: 19.5*q}
        totale += p_str.get(ore, 0)
    return totale

# --- TASTIERE ---
def menu_utente():
    kb = [[InlineKeyboardButton("📢 Sponsor Standard", callback_data='sel_std')],
          [InlineKeyboardButton("🚀 Incrementi", callback_data='menu_inc')],
          [InlineKeyboardButton("📋 Listino", url='https://t.me/tuochannel')]]
    return InlineKeyboardMarkup(kb)

def tastiera_selezione_mista(selezionati):
    kb = []
    for c in CANALI_STANDARD_FISSI:
        s = " ✅" if c in selezionati else ""
        kb.append([InlineKeyboardButton(f"{c}{s}", callback_data=f"t_{c}")])
    kb.append([InlineKeyboardButton("📺 CANALI STREAMING 📺", callback_data="none")])
    row = []
    for i, c in enumerate(CANALI_STREAMING):
        num = c.split()[1]
        s = "✅" if c in selezionati else num
        row.append(InlineKeyboardButton(f"Str {s}", callback_data=f"t_{c}"))
        if len(row) == 3:
            kb.append(row); row = []
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
        kb = [[InlineKeyboardButton("📊 Vedi Ordini (Admin)", callback_data='admin_orders')], [InlineKeyboardButton("🌐 Vista Utente", callback_data='back_to_start')]]
        txt = "<b>👮‍♂️ PANNELLO ADMIN</b>"
        await (update.callback_query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML') if update.callback_query else update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML'))
    else:
        txt = "👋 <b>Benvenuto!</b> Scegli un'opzione:"
        await (update.callback_query.edit_message_text(txt, reply_markup=menu_utente(), parse_mode='HTML') if update.callback_query else update.message.reply_text(txt, reply_markup=menu_utente(), parse_mode='HTML'))

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
        if 'sel' not in u_data: u_data['sel'] = []
        if c in u_data['sel']: u_data['sel'].remove(c)
        else: u_data['sel'].append(c)
        await query.edit_message_reply_markup(reply_markup=tastiera_selezione_mista(u_data['sel']))

    elif data == 'all_str':
        if 'sel' not in u_data: u_data['sel'] = []
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
        u_data['ore'] = int(data.replace('h_', ''))
        u_data['prezzo'] = calcola_prezzo_finale(u_data['sel'], u_data['ore'])
        kb = [[InlineKeyboardButton("📅 SCEGLI DATA", callback_data="choose_date")], [InlineKeyboardButton("⬅️ Indietro", callback_data="go_durata")]]
        await query.edit_message_text(f"🛒 <b>RIEPILOGO</b>\nCanali: {len(u_data['sel'])}\nDurata: {u_data['ore']}h\n💰 <b>Totale: {u_data['prezzo']}€</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data == 'menu_inc':
        kb = [[InlineKeyboardButton(f"{k} - {v}€", callback_data=f"buy_inc_{k}")] for k, v in PREZZI_INCREMENTI.items()]
        kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")])
        await query.edit_message_text("🚀 <b>INCREMENTI</b>\nScegli il pacchetto:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data.startswith('buy_inc_'):
        pacco = data.replace('buy_inc_', '')
        u_data['tipo'] = "Incremento"
        u_data['dettaglio'] = pacco
        u_data['prezzo'] = PREZZI_INCREMENTI[pacco]
        kb = [[InlineKeyboardButton("💳 CONFERMA ORDINE", callback_data="confirm_order")], [InlineKeyboardButton("⬅️ Indietro", callback_data="menu_inc")]]
        await query.edit_message_text(f"🚀 Pacchetto scelto: {pacco}\n💰 Prezzo: {u_data['prezzo']}€\n\nConfermi l'ordine?", reply_markup=InlineKeyboardMarkup(kb))

    elif data == 'choose_date':
        # Calendario semplice per test
        kb = []
        oggi = datetime.now()
        for i in range(1, 6):
            giorno = (oggi + timedelta(days=i)).strftime("%d/%m")
            kb.append([InlineKeyboardButton(f"🟢 {giorno}", callback_data=f"final_date_{giorno}")])
        await query.edit_message_text("Seleziona il giorno:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith('final_date_'):
        u_data['data'] = data.replace('final_date_', '')
        await query.edit_message_text(f"Hai scelto il {u_data['data']}.\n\n✅ <b>CONFERMA FINALE</b>\nCanali: {len(u_data['sel'])}\nPrezzo: {u_data['prezzo']}€\n\nInviare la richiesta?",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ INVIA", callback_data="confirm_order")]]))

    elif data == "confirm_order":
        user = update.effective_user
        info = f"💰 <b>NUOVO ORDINE!</b>\n\n👤 Utente: @{user.username} (ID: {user.id})\n"
        if u_data.get('tipo') == "Incremento":
            info += f"📦 Tipo: Incremento\n📊 Pacchetto: {u_data['dettaglio']}\n💰 Totale: {u_data['prezzo']}€"
        else:
            info += f"📢 Tipo: Sponsor\n📅 Data: {u_data.get('data')}\n⏱ Durata: {u_data.get('ore')}h\n💰 Totale: {u_data.get('prezzo')}€"

        await context.bot.send_message(chat_id=ADMIN_ID, text=info, parse_mode='HTML')
        await query.edit_message_text("✅ <b>Richiesta inviata!</b>\nTi contatteremo a breve per il pagamento (Bonifico/PostePay/Revolut).")

    elif data == 'back_to_start': await start(update, context)

if __name__ == '__main__':
    Thread(target=run).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(CallbackQueryHandler(gestore_callback))
    bot.run_polling()
