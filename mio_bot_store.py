import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# --- CONFIGURAZIONE ---
TOKEN = "IL_TUO_NUOVO_TOKEN"
ADMIN_ID = 1457338119  # Il tuo ID Telegram

# Simulazione Database (In una versione pro useremo un DB vero)
# Struttura: { "2024-04-20_09:00": {"user": "@utente", "tipo": "Sponsor", "canale": "Standard"} }
PRENOTAZIONI = {}

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- TASTIERE ---

def menu_principale(user_id):
    keyboard = [
        [InlineKeyboardButton("📢 Acquista Sponsor", callback_data='menu_sponsor')],
        [InlineKeyboardButton("🚀 Acquista Incrementi", callback_data='menu_incrementi')],
        [InlineKeyboardButton("📦 Stato Ordine", callback_data='stato_ordine'),
         InlineKeyboardButton("🎧 Assistenza", callback_data='assistenza')],
        [InlineKeyboardButton("📋 Listino Prezzi", url='https://t.me/tuo_canale_prezzi')],
        [InlineKeyboardButton("❓ Come funziona", callback_data='come_funziona')]
    ]
    # Se l'utente sei tu, aggiungiamo il tasto segreto Admin
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👮‍♂️ PANNELLO ADMIN", callback_data='admin_home')])

    return InlineKeyboardMarkup(keyboard)

def menu_admin():
    kb = [
        [InlineKeyboardButton("📅 Calendario Prenotazioni", callback_data='admin_view_booked')],
        [InlineKeyboardButton("✅ Date Disponibili", callback_data='admin_view_free')],
        [InlineKeyboardButton("⬅️ Torna al Menu", callback_data='back_to_start')]
    ]
    return InlineKeyboardMarkup(kb)

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    txt = f"👋 <b>Ciao {user.first_name}!</b>\nBenvenuto nello Store. Cosa desideri fare?"

    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=menu_principale(user.id), parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=menu_principale(user.id), parse_mode='HTML')

async def gestore_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == 'admin_home':
        await query.edit_message_text("<b>👮‍♂️ AREA AMMINISTRATORE</b>\n\nQui puoi gestire le prenotazioni e vedere gli ordini.",
                                     reply_markup=menu_admin(), parse_mode='HTML')

    elif data == 'admin_view_booked':
        if not PRENOTAZIONI:
            txt = "📭 <b>Nessuna prenotazione attiva al momento.</b>"
        else:
            txt = "📅 <b>LISTA PRENOTAZIONI:</b>\n\n"
            for data_ora, info in PRENOTAZIONI.items():
                txt += f"• 🗓 {data_ora}\n  👤 Utente: {info['user']}\n  📦 {info['tipo']} - {info['canale']}\n\n"

        await query.edit_message_text(txt, reply_markup=menu_admin(), parse_mode='HTML')

    elif data == 'admin_view_free':
        # Qui in futuro metteremo la logica per vedere i giorni vuoti del mese
        await query.edit_message_text("🗓 <b>DETTAGLIO DISPONIBILITÀ</b>\n\nQuesta funzione mostrerà i giorni liberi nel calendario.",
                                     reply_markup=menu_admin(), parse_mode='HTML')

async def gestore_callback_generale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # Gestione delle sezioni utente (Sponsor, Incrementi, etc.)
    if data == 'menu_incrementi':
        # ... logica degli incrementi che abbiamo scritto prima ...
        pass

    elif data == 'back_to_start':
        await start(update, context)

    # Reindirizza i click admin alla funzione dedicata
    if data.startswith('admin_'):
        await gestore_admin(update, context)

# --- MAIN ---
if __name__ == '__main__':
    bot_app = ApplicationBuilder().token(TOKEN).build()

    bot_app.add_handler(CommandHandler('start', start))
    bot_app.add_handler(CallbackQueryHandler(gestore_callback_generale))

    print("Bot in ascolto...")
    bot_app.run_polling()