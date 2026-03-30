import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from flask import Flask
from threading import Thread

# --- CONFIGURAZIONE DIRETTA ---
TOKEN = "8601357271:AAEmVAdioTlrZ5nMAwZgOwM7U-ggmp_flL4"
ADMIN_ID = 8361466889

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATI CANALI E PREZZI ---
CANALI_STREAMING = [f"Streaming {i}" for i in range(1, 10)]
PREZZI_STANDARD = {
    "Goal": {3: 5, 6: 7.5, 12: 11, 24: 13.5},
    "Juventus Planet": {3: 4, 6: 5.5, 12: 8, 24: 12}
}

def calcola_prezzo_streaming(quantita, ore):
    if quantita == 9: prezzi = {3: 25, 6: 35, 12: 50, 24: 65}
    elif 5 <= quantita <= 8: prezzi = {3: 20, 6: 30, 12: 40, 24: 50}
    elif 3 <= quantita <= 4: prezzi = {3: 15, 6: 20, 12: 35, 24: 45}
    else: prezzi = {3: 6 * quantita, 6: 9.5 * quantita, 12: 15 * quantita, 24: 19.5 * quantita}
    return prezzi.get(ore, 0)

# --- TASTIERE ---
def menu_principale():
    kb = [
        [InlineKeyboardButton("📢 Acquista Sponsor", callback_data='menu_sponsor')],
        [InlineKeyboardButton("🚀 Acquista Incrementi", callback_data='menu_incrementi')],
        [InlineKeyboardButton("📋 Listino Prezzi", url='https://t.me/tuochannel')],
        [InlineKeyboardButton("❓ Come funziona", callback_data='come_funziona')]
    ]
    return InlineKeyboardMarkup(kb)

def tastiera_streaming(selezionati):
    kb = []
    row = []
    for i, nome in enumerate(CANALI_STREAMING):
        spunta = " ✅" if nome in selezionati else ""
        row.append(InlineKeyboardButton(f"{nome}{spunta}", callback_data=f"toggle_{nome}"))
        if len(row) == 3:
            kb.append(row)
            row = []
    kb.append([InlineKeyboardButton("✨ Seleziona Tutti", callback_data="select_all_st")])
    kb.append([InlineKeyboardButton("➡️ AVANTI", callback_data="go_durata")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="menu_sponsor")])
    return InlineKeyboardMarkup(kb)

def tastiera_aggiunte(u_data):
    r = "✅ " if u_data.get('repost') else ""
    f = "✅ " if u_data.get('fissato') else ""
    n = u_data.get('nopost', 0)
    kb = [
        [InlineKeyboardButton(f"{r}Repost (+3€)", callback_data="btn_repost")],
        [InlineKeyboardButton(f"{f}Fissato (+1€)", callback_data="btn_fissato")],
        [InlineKeyboardButton(f"⏳ No-Post: {n}/3h", callback_data="btn_nopost")],
        [InlineKeyboardButton("📅 PROCEDI AL CALENDARIO", callback_data="go_calendario")],
        [InlineKeyboardButton("⬅️ Indietro", callback_data="menu_sponsor")]
    ]
    return InlineKeyboardMarkup(kb)

# --- LOGICA SERVER PER RENDER ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Bot is Social!"
def run(): webapp.run(host='0.0.0.0', port=10000)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    txt = "👋 <b>Benvenuto nello Store!</b>\nCosa vuoi prenotare oggi?"
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=menu_principale(), parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=menu_principale(), parse_mode='HTML')

async def gestore_bottoni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = context.user_data
    data = query.data
    await query.answer()

    if data == 'menu_sponsor':
        kb = [[InlineKeyboardButton("⚽ Standard (Goal/Juve)", callback_data='cat_std')],
              [InlineKeyboardButton("📺 Streaming (1-9)", callback_data='cat_str')],
              [InlineKeyboardButton("⬅️ Indietro", callback_data='back_to_start')]]
        await query.edit_message_text("Seleziona categoria:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == 'cat_str':
        u_data['tipo'] = 'streaming'
        u_data['sel_canali'] = u_data.get('sel_canali', [])
        await query.edit_message_text("Seleziona i canali Streaming:", reply_markup=tastiera_streaming(u_data['sel_canali']))

    elif data.startswith('toggle_'):
        c = data.replace('toggle_', '')
        if c in u_data['sel_canali']: u_data['sel_canali'].remove(c)
        else: u_data['sel_canali'].append(c)
        await query.edit_message_reply_markup(reply_markup=tastiera_streaming(u_data['sel_canali']))

    elif data == 'select_all_st':
        u_data['sel_canali'] = list(CANALI_STREAMING)
        await query.edit_message_reply_markup(reply_markup=tastiera_streaming(u_data['sel_canali']))

    elif data == 'go_durata':
        if not u_data.get('sel_canali'): return await query.answer("Seleziona almeno un canale!", show_alert=True)
        kb = [[InlineKeyboardButton("3h", callback_data="h_3"), InlineKeyboardButton("6h", callback_data="h_6")],
              [InlineKeyboardButton("12h", callback_data="h_12"), InlineKeyboardButton("24h", callback_data="h_24")],
              [InlineKeyboardButton("⬅️ Indietro", callback_data="menu_sponsor")]]
        await query.edit_message_text("Scegli la durata della sponsor:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith('h_'):
        u_data['ore'] = int(data.replace('h_', ''))
        await query.edit_message_text("Seleziona le aggiunte desiderate:", reply_markup=tastiera_aggiunte(u_data))

    elif data == 'btn_repost':
        u_data['repost'] = not u_data.get('repost', False)
        await query.edit_message_reply_markup(reply_markup=tastiera_aggiunte(u_data))

    elif data == 'btn_fissato':
        u_data['fissato'] = not u_data.get('fissato', False)
        await query.edit_message_reply_markup(reply_markup=tastiera_aggiunte(u_data))

    elif data == 'btn_nopost':
        curr = u_data.get('nopost', 0)
        u_data['nopost'] = curr + 1 if curr < 3 else 0
        await query.edit_message_reply_markup(reply_markup=tastiera_aggiunte(u_data))

    elif data == 'go_calendario':
        await query.edit_message_text("🚧 Sezione Calendario in arrivo...\n(Stiamo configurando i pallini rossi 🔴)")

    elif data == 'back_to_start':
        await start(update, context)

if __name__ == '__main__':
    Thread(target=run).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(CallbackQueryHandler(gestore_bottoni))
    bot.run_polling()
