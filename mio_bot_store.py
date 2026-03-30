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
CANALI_STD = ["Goal", "Juventus Planet"]
PREZZI_STD = {
    "Goal": {3: 5, 6: 7.5, 12: 11, 24: 13.5},
    "Juventus Planet": {3: 4, 6: 5.5, 12: 8, 24: 12}
}

# --- TASTIERE ---

def menu_admin():
    kb = [
        [InlineKeyboardButton("📅 CALENDARIO (🔴/🟢)", callback_data='admin_cal')],
        [InlineKeyboardButton("💰 ORDINI RICEVUTI", callback_data='admin_orders')],
        [InlineKeyboardButton("🌐 VEDI COME UTENTE", callback_data='back_to_start')]
    ]
    return InlineKeyboardMarkup(kb)

def menu_utente():
    kb = [
        [InlineKeyboardButton("📢 Sponsor Standard", callback_data='sel_std')],
        [InlineKeyboardButton("🚀 Incrementi", callback_data='menu_incrementi')],
        [InlineKeyboardButton("📋 Listino Prezzi", url='https://t.me/tuochannel')],
        [InlineKeyboardButton("❓ Come funziona", callback_data='come_funziona')]
    ]
    return InlineKeyboardMarkup(kb)

def tastiera_canali_std(selezionati):
    kb = []
    for canale in CANALI_STD:
        spunta = " ✅" if canale in selezionati else ""
        kb.append([InlineKeyboardButton(f"{canale}{spunta}", callback_data=f"toggle_std_{canale}")])

    kb.append([InlineKeyboardButton("➡️ AVANTI", callback_data="go_durata_std")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")])
    return InlineKeyboardMarkup(kb)

# --- SERVER WEB ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Online"
def run(): webapp.run(host='0.0.0.0', port=10000)

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear() # Reset carrello

    if user_id == ADMIN_ID:
        txt = "<b>👮‍♂️ PANNELLO ADMIN</b>\nGestisci prenotazioni e disponibilità."
        reply_markup = menu_admin()
    else:
        txt = "👋 <b>Benvenuto nello Store!</b>\nCosa desideri acquistare?"
        reply_markup = menu_utente()

    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=reply_markup, parse_mode='HTML')

async def gestore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    u_data = context.user_data
    user_id = update.effective_user.id
    await query.answer()

    # --- LOGICA UTENTE ---
    if data == 'sel_std':
        u_data['sel_canali'] = u_data.get('sel_canali', [])
        await query.edit_message_text("Seleziona i canali per la Sponsor Standard:",
                                     reply_markup=tastiera_canali_std(u_data['sel_canali']))

    elif data.startswith('toggle_std_'):
        canale = data.replace('toggle_std_', '')
        if canale in u_data['sel_canali']: u_data['sel_canali'].remove(canale)
        else: u_data['sel_canali'].append(canale)
        await query.edit_message_reply_markup(reply_markup=tastiera_canali_std(u_data['sel_canali']))

    elif data == 'go_durata_std':
        if not u_data.get('sel_canali'):
            await query.answer("Seleziona almeno un canale!", show_alert=True)
            return
        kb = [[InlineKeyboardButton("3h", callback_data="h_3"), InlineKeyboardButton("6h", callback_data="h_6")],
              [InlineKeyboardButton("12h", callback_data="h_12"), InlineKeyboardButton("24h", callback_data="h_24")],
              [InlineKeyboardButton("⬅️ Indietro", callback_data="sel_std")]]
        await query.edit_message_text("Scegli la durata:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == 'menu_incrementi':
        await query.edit_message_text("🚀 <b>SEZIONE INCREMENTI</b>\n\n(Invia i prezzi quando vuoi per attivarla!)",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data='back_to_start')]]),
                                     parse_mode='HTML')

    # --- LOGICA ADMIN ---
    elif data == 'admin_cal' and user_id == ADMIN_ID:
        await query.edit_message_text("📅 <b>CALENDARIO DINAMICO</b>\n\n🟢 01/04 | 🟢 02/04 | 🔴 03/04\n\n(Sistema in fase di attivazione...)",
                                     reply_markup=menu_admin(), parse_mode='HTML')

    elif data == 'back_to_start':
        await start(update, context)

if __name__ == '__main__':
    Thread(target=run).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(CallbackQueryHandler(gestore_callback))
    bot.run_polling()
