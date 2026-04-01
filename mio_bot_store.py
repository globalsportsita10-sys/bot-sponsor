import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from flask import Flask
from threading import Thread

# --- 1. CONFIGURAZIONE ---
TOKEN = "8601357271:AAEmVAdioTlrZ5nMAwZgOwM7U-ggmp_flL4"
ADMIN_ID = 8361466889

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 2. DATI E LISTINI ---
CANALI_FISSI = {"Goal": "⚽️ Goal", "Juve": "🦓 Juventus Planet"}
CANALI_STR = {f"Str{i}": f"🖥 Streaming {i}" for i in range(1, 10)}
ALL_CH = {**CANALI_FISSI, **CANALI_STR}

PACCHETTI_INC = {
    "1k": "50€", "2k": "80€", "5k": "180€", "10k": "330€",
    "15k": "460€", "20k": "580€", "25k": "690€", "30k": "780€"
}

# --- 3. TASTIERE ---
def kb_home(u_id):
    kb = [
        [InlineKeyboardButton("📢 Acquista Sponsor", callback_data="m_sp")],
        [InlineKeyboardButton("📈 Acquista Incrementi", callback_data="m_inc")],
        [InlineKeyboardButton("🎁 Stato Ordine", callback_data="status"), InlineKeyboardButton("🆘 Assistenza", callback_data="help")],
        [InlineKeyboardButton("💰 Listino Prezzi ↗️", url="https://t.me/listinoSoccerHubOff")],
        [InlineKeyboardButton("⚠️ T&C ↗️", callback_data="tc"), InlineKeyboardButton("ℹ️ Come Funziona", callback_data="how")]
    ]
    if u_id == ADMIN_ID: kb.insert(0, [InlineKeyboardButton("👮‍♂️ PANNELLO ADMIN", callback_data="adm")])
    return InlineKeyboardMarkup(kb)

def kb_canali(sel):
    kb = []
    kb.append([InlineKeyboardButton(f"{'✅ ' if c in sel else ''}{n}", callback_data=f"t_{c}") for c, n in CANALI_FISSI.items()])
    row = []
    for i in range(1, 10):
        cid = f"Str{i}"; row.append(InlineKeyboardButton(f"{'✅ ' if cid in sel else ''}S{i}", callback_data=f"t_{cid}"))
        if len(row) == 3: kb.append(row); row = []
    kb.append([InlineKeyboardButton("✨ Seleziona Tutti", callback_data="s_all"), InlineKeyboardButton("❌ Svuota", callback_data="s_none")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="m_sp"), InlineKeyboardButton("Avanti ➡️", callback_data="go_h")])
    return InlineKeyboardMarkup(kb)

# --- 4. GESTIONE CLIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    txt = "👋 <b>Benvenuto su SoccerHub!</b>\n\n🟢 Servizio ufficiale sponsor e incrementi.\n\n👇 <b>Scegli un servizio:</b>"
    if update.callback_query: await update.callback_query.edit_message_text(txt, reply_markup=kb_home(update.effective_user.id), parse_mode='HTML')
    else: await update.message.reply_text(txt, reply_markup=kb_home(update.effective_user.id), parse_mode='HTML')

async def handling_clic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = context.user_data
    await q.answer()

    # --- MENU PRINCIPALE ---
    if q.data == "back": await start(update, context)
    elif q.data == "help":
        await q.edit_message_text("🆘 <b>ASSISTENZA</b>\n\nAdmin: @Calogero7\nBot: @SoccerPassionLimitatibot", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="back")]]), parse_mode='HTML')
    elif q.data == "tc":
        await q.edit_message_text("⚠️ <b>TERMINI E CONDIZIONI</b>\n\n1. No contenuti illegali.\n2. Pagamento anticipato.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="back")]]), parse_mode='HTML')

    # --- SEZIONE INCREMENTI (Tua richiesta specifica) ---
    elif q.data == "m_inc":
        kb = []
        keys = list(PACCHETTI_INC.keys())
        for i in range(0, len(keys), 2):
            row = [InlineKeyboardButton(f"🔹 {k} ⇨ {PACCHETTI_INC[k]}", callback_data=f"buyinc_{k}") for k in keys[i:i+2]]
            kb.append(row)
        kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back")])
        await q.edit_message_text("📈 <b>INCREMENTI ISCRITTI</b>\nScegli il pacchetto desiderato:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif q.data.startswith("buyinc_"):
        pck = q.data.split("_")[1]
        u['pacc'] = pck
        u['state'] = 'WAIT_INC_FORWARD'
        txt = (f"<b>Pacchetto scelto:</b> {pck} iscritti\n"
               f"<b>Prezzo:</b> {PACCHETTI_INC[pck]}\n\n"
               "🛠 <b>ISTRUZIONI:</b>\n"
               "1️⃣ Aggiungi il nostro bot come Amministratore nel tuo canale.\n"
               "2️⃣ <b>INOLTRA QUI</b> un messaggio dal tuo canale per confermare.")
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Annulla", callback_data="m_inc")]]), parse_mode='HTML')

    # --- SEZIONE SPONSOR ---
    elif q.data == "m_sp":
        kb = [[InlineKeyboardButton("🌐 Canale Standard", callback_data="sp_std")],[InlineKeyboardButton("⬅️ Indietro", callback_data="back")]]
        await q.edit_message_text("⚖️ <b>Tipo di contenuto?</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif q.data == "sp_std":
        u['sel'] = u.get('sel', [])
        await q.edit_message_text("👇 <b>Seleziona i canali:</b>", reply_markup=kb_canali(u['sel']), parse_mode='HTML')

    elif q.data.startswith("t_"):
        c = q.data.split("_")[1]
        if c in u.get('sel', []): u['sel'].remove(c)
        else: u.setdefault('sel', []).append(c)
        await q.edit_message_reply_markup(reply_markup=kb_canali(u['sel']))

# --- 5. GESTIONE MESSAGGI (INOLTRI) ---
async def ricevi_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = context.user_data
    if u.get('state') == 'WAIT_INC_FORWARD':
        if update.message.forward_from_chat:
            cid = update.message.forward_from_chat.title
            await update.message.reply_text(f"✅ <b>Canale Rilevato:</b> {cid}\nL'ordine per {u['pacc']} iscritti è stato registrato. Verrai contattato per il pagamento.")
            u['state'] = None
        else:
            await update.message.reply_text("❌ Devi <b>INOLTRARE</b> un messaggio dal tuo canale, non scriverlo!")

# --- 6. SERVER WEB ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot Online"

if __name__ == '__main__':
    Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000)).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CallbackQueryHandler(handling_clic))
    bot.add_handler(MessageHandler(filters.ALL, ricevi_msg))
    bot.run_polling()
