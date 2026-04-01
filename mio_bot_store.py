import logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from flask import Flask
from threading import Thread

# --- CONFIGURAZIONE ---
TOKEN = "8601357271:AAEmVAdioTlrZ5nMAwZgOwM7U-ggmp_flL4"
ADMIN_ID = 8361466889

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- I TUOI DATI ---
CANALI_FISSI = {"Goal": "⚽️ Goal", "Juventus Planet": "🦓 Juventus Planet"}
CANALI_STR = {f"Streaming {i}": f"🖥 Streaming {i}" for i in range(1, 10)}
TUTTI_I_CANALI = {**CANALI_FISSI, **CANALI_STR}

# --- TASTIERE ---
def kb_home(u_id):
    kb = [
        [InlineKeyboardButton("📢 Acquista Sponsor", callback_data="buy_sp")],
        [InlineKeyboardButton("📈 Acquista Incrementi", callback_data="buy_inc")],
        [InlineKeyboardButton("🎁 Stato Ordine", callback_data="st_ord"), InlineKeyboardButton("🆘 Assistenza", callback_data="assist")],
        [InlineKeyboardButton("💰 Listino Prezzi ↗️", url="https://t.me/listinoSoccerHubOff")],
        [InlineKeyboardButton("⚠️ T&C ↗️", callback_data="tc_page"), InlineKeyboardButton("ℹ️ Come Funziona", callback_data="info_how")]
    ]
    if u_id == ADMIN_ID:
        kb.insert(0, [InlineKeyboardButton("👮‍♂️ PANNELLO ADMIN", callback_data="adm_panel")])
    return InlineKeyboardMarkup(kb)

def kb_canali(sel):
    buttons = []
    row_fissi = [InlineKeyboardButton(f"{'✅ ' if c in sel else ''}{n}", callback_data=f"t_{c}") for c, n in CANALI_FISSI.items()]
    buttons.append(row_fissi)
    row = []
    for i in range(1, 10):
        cid = f"Streaming {i}"
        row.append(InlineKeyboardButton(f"{'✅ ' if cid in sel else ''}Str {i}", callback_data=f"t_{cid}"))
        if len(row) == 3: buttons.append(row); row = []
    buttons.append([InlineKeyboardButton("✨ Seleziona Tutti", callback_data="all_on")])
    buttons.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back"), InlineKeyboardButton("Avanti ➡️", callback_data="go_h")])
    return InlineKeyboardMarkup(buttons)

# --- FUNZIONI RISPOSTA ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_id = update.effective_user.id
    context.user_data['sel'] = [] # Reset selezione
    txt = "👋 <b>Benvenuto su SoccerHub!</b>\n\n👇 <b>Scegli il servizio:</b>"
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb_home(u_id), parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=kb_home(u_id), parse_mode='HTML')

async def gestione_clic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_id = update.effective_user.id
    data = query.data
    u_data = context.user_data
    await query.answer() # Rimuove l'icona dell'orologio sul tasto

    if data == "back":
        await start(update, context)

    elif data == "buy_sp":
        kb = [[InlineKeyboardButton("🌐 Canale Standard", callback_data="std")],[InlineKeyboardButton("🏴‍☠️ IPTV/Vendita", callback_data="iptv")],[InlineKeyboardButton("⬅️ Indietro", callback_data="back")]]
        await query.edit_message_text("⚖️ <b>Tipo di contenuto?</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data == "std":
        u_data['sel'] = u_data.get('sel', [])
        await query.edit_message_text("👇 <b>Seleziona i canali:</b>", reply_markup=kb_canali(u_data['sel']), parse_mode='HTML')

    elif data.startswith("t_"):
        canale = data.split("_")[1]
        u_data['sel'] = u_data.get('sel', [])
        if canale in u_data['sel']: u_data['sel'].remove(canale)
        else: u_data['sel'].append(canale)
        await query.edit_message_reply_markup(reply_markup=kb_canali(u_data['sel']))

    elif data == "assist":
        txt = "🆘 <b>ASSISTENZA</b>\n\n👤 Admin: @Calogero7\n🤖 Supporto: @SoccerPassionLimitatibot"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="back")]]), parse_mode='HTML')

    elif data == "info_how":
        txt = "⚙️ <b>COME FUNZIONA</b>\n\n1. Scegli i canali\n2. Prenota data/ora\n3. Invia il post\n4. Paga e vai online!"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="back")]]), parse_mode='HTML')

# --- AVVIO SERVER ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Bot Online"

if __name__ == '__main__':
    Thread(target=lambda: webapp.run(host='0.0.0.0', port=10000)).start()
    app = ApplicationBuilder().token(TOKEN).build()

    # AGGIUNTA HANDLERS
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(gestione_clic)) # QUESTA RIGA DEVE ESSERE ESATTAMENTE COSÌ

    print("Bot in ascolto...")
    app.run_polling()
