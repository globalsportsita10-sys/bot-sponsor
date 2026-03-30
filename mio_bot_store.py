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

# --- DATABASE TEMPORANEO (Si resetta se il server si spegne, per database fisso serve SQL) ---
prenotazioni = {} # Esempio: {"2024-04-01": [(9, 12), (15, 18)]}

# --- DATI PREZZI ---
PREZZI_INCREMENTI = {"1K": 50, "2K": 80, "3K": 120, "5K": 200}
CANALI_STD_FISSI = ["Goal", "Juventus Planet"]
CANALI_STREAMING = [f"Streaming {i}" for i in range(1, 10)]

# --- LOGICA CALCOLI ---
def calcola_prezzo_sponsor(sel, ore):
    totale = 0
    prezzi_fissi = {"Goal": {3: 5, 6: 7.5, 12: 11, 24: 13.5}, "Juventus Planet": {3: 4, 6: 5.5, 12: 8, 24: 12}}
    for c in CANALI_STD_FISSI:
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

def tastiera_calendario():
    kb = []
    oggi = datetime.now()
    for i in range(1, 8): # Prossimi 7 giorni
        giorno = (oggi + timedelta(days=i)).strftime("%d/%m")
        data_key = (oggi + timedelta(days=i)).strftime("%Y-%m-%d")
        status = "🔴" if data_key in prenotazioni and len(prenotazioni[data_key]) >= 4 else "🟢"
        kb.append([InlineKeyboardButton(f"{status} {giorno}", callback_data=f"date_{data_key}")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")])
    return InlineKeyboardMarkup(kb)

# --- SERVER WEB ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Bot Online"
def run(): webapp.run(host='0.0.0.0', port=10000)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_id = update.effective_user.id
    context.user_data.clear()
    if u_id == ADMIN_ID:
        txt = "<b>👮‍♂️ ADMIN PANEL</b>"
        kb = [[InlineKeyboardButton("📊 Vedi Ordini", callback_data='admin_orders')], [InlineKeyboardButton("🌐 Vista Utente", callback_data='back_to_start')]]
        await (update.callback_query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML') if update.callback_query else update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML'))
    else:
        await (update.callback_query.edit_message_text("Benvenuto! Scegli:", reply_markup=menu_utente()) if update.callback_query else update.message.reply_text("Benvenuto! Scegli:", reply_markup=menu_utente()))

async def gestore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    u_data = context.user_data
    await query.answer()

    if data == 'menu_inc':
        kb = [[InlineKeyboardButton(f"{k} - {v}€", callback_data=f"buy_inc_{k}")] for k, v in PREZZI_INCREMENTI.items()]
        kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")])
        await query.edit_message_text("🚀 <b>INCREMENTI</b>\nScegli il pacchetto:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data == 'sel_std':
        # Logica selezione canali (omessa per brevità, usa quella del messaggio precedente)
        pass

    elif data.startswith('date_'):
        data_sel = data.replace('date_', '')
        u_data['data'] = data_sel
        kb = [[InlineKeyboardButton("09:00 - 12:00", callback_data="time_09_12")],
              [InlineKeyboardButton("15:00 - 18:00", callback_data="time_15_18")],
              [InlineKeyboardButton("21:00 - 00:00", callback_data="time_21_00")]]
        await query.edit_message_text(f"Scegli l'orario per il {data_sel}:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith('time_'):
        u_data['ora'] = data.replace('time_', '')
        txt = f"✅ <b>ORDINE PRONTO</b>\nPagamento: Bonifico (PostePay/Revolut)\n\nClicca sotto per confermare e inviare la richiesta."
        kb = [[InlineKeyboardButton("💳 CONFERMA E INVIA", callback_data="confirm_order")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data == "confirm_order":
        msg_admin = f"💰 <b>NUOVO ORDINE!</b>\nUtente: @{update.effective_user.username}\nTipo: {u_data.get('type', 'Sponsor')}\nDettagli: {u_data}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg_admin, parse_mode='HTML')
        await query.edit_message_text("✅ Richiesta inviata! Verrai contattato a breve per il pagamento.")

    elif data == 'back_to_start': await start(update, context)

if __name__ == '__main__':
    Thread(target=run).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(CallbackQueryHandler(gestore_callback))
    bot.run_polling()
