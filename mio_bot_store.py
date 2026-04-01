import logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from flask import Flask
from threading import Thread

# --- 1. CONFIGURAZIONE E CONTATTI ---
TOKEN = "8601357271:AAEmVAdioTlrZ5nMAwZgOwM7U-ggmp_flL4"
ADMIN_ID = 8361466889
LINK_LISTINO = "https://t.me/listinoSoccerHubOff"
CONTATTO_ADMIN = "@Calogero7"
BOT_SUPPORTO = "@SoccerPassionLimitatibot"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 2. TASTIERE PRINCIPALI ---
def kb_home(u_id):
    kb = [
        [InlineKeyboardButton("📢 Acquista Sponsor", callback_data="buy_sp")],
        [InlineKeyboardButton("📈 Acquista Incrementi", callback_data="buy_inc")],
        [InlineKeyboardButton("🎁 Stato Ordine", callback_data="st_ord"), InlineKeyboardButton("🆘 Assistenza", callback_data="assist")],
        [InlineKeyboardButton("💰 Listino Prezzi ↗️", url=LINK_LISTINO), InlineKeyboardButton("⚠️ T&C ↗️", callback_data="tc_page")],
        [InlineKeyboardButton("ℹ️ Come Funziona", callback_data="info_how")]
    ]
    if u_id == ADMIN_ID:
        kb.insert(0, [InlineKeyboardButton("👮‍♂️ PANNELLO ADMIN", callback_data="adm_panel")])
    return InlineKeyboardMarkup(kb)

# --- 3. HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_id = update.effective_user.id
    txt = "👋 <b>Benvenuto su SoccerHub!</b>\n\n🟢 Il servizio ufficiale per sponsorizzazioni e incremento iscritti sul nostro network di canali dedicati al calcio.\n\n👇 <b>Scegli il servizio di cui hai bisogno:</b>"
    kb = kb_home(u_id)
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode='HTML')

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # --- SEZIONE COME FUNZIONA (Dal tuo screenshot) ---
    if q.data == "info_how":
        txt = (
            "⚙️ <b>COME FUNZIONA IL BOT</b>\n\n"
            "Prenotare è semplice e automatizzato. Ecco i passaggi:\n\n"
            "📢 <b>PER LE SPONSORIZZAZIONI:</b>\n"
            "1️⃣ <b>Scegli</b> i canali, la durata e le opzioni extra (Repost, Fissato).\n"
            "2️⃣ <b>Prenota</b> la data e l'orario esatto dal calendario.\n"
            "3️⃣ <b>Invia</b> il post in chat (<i>ti consigliamo di preparare il post prima con @chelpbot</i>).\n"
            "4️⃣ <b>Attendi</b> la rapida approvazione dell'amministratore.\n"
            "5️⃣ <b>Paga</b> in sicurezza. Il post andrà online all'orario stabilito!\n\n"
            "📈 <b>PER GLI INCREMENTI:</b>\n"
            "1️⃣ <b>Seleziona</b> il target di iscritti desiderato.\n"
            "2️⃣ <b>Aggiungi</b> temporaneamente il nostro bot di servizio al tuo canale.\n"
            "3️⃣ <b>Inoltra</b> un messaggio dal tuo canale a questa chat.\n"
            "4️⃣ <b>Paga</b> per avviare subito la campagna di crescita.\n\n"
            "💡 <i>Per problemi o richieste particolari, usa il tasto Assistenza nel menu.</i>"
        )
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Torna al Menu", callback_data="back")]]), parse_mode='HTML')

    # --- SEZIONE ADMIN (Dal tuo screenshot) ---
    elif q.data == "adm_panel":
        txt = "👮‍♂️ <b>PANNELLO ADMIN</b>"
        kb = [
            [InlineKeyboardButton("📊 Gestisci Ordini", callback_data="adm_orders")],
            [InlineKeyboardButton("🌐 Visita Utente", callback_data="adm_user")],
            [InlineKeyboardButton("⬅️ Indietro", callback_data="back")]
        ]
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif q.data == "assist":
        txt = f"🆘 <b>ASSISTENZA E SUPPORTO</b>\n\nHai domande su un <b>ordine</b>, problemi <b>tecnici</b> o vuoi maggiori informazioni? Contatta il nostro team:\n\n👤 Amministratore: {CONTATTO_ADMIN}\n🤖 Bot ufficiale: {BOT_SUPPORTO}\n\n<i>Di solito rispondiamo entro poche ore.</i>"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Torna al Menu", callback_data="back")]]), parse_mode='HTML')

    elif q.data == "back":
        await start(update, context)

# --- 4. SERVER PER RENDER ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Bot SoccerHub Online"
def run_flask(): webapp.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    Thread(target=run_flask).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(callback))
    app.run_polling()
