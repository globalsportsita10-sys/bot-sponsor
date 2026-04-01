import logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from flask import Flask
from threading import Thread

# --- 1. CONFIGURAZIONE ---
TOKEN = "8601357271:AAEmVAdioTlrZ5nMAwZgOwM7U-ggmp_flL4"
ADMIN_ID = 8361466889

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 2. I TUOI DATI ---
CANALI_FISSI = {"Goal": "⚽️ Goal", "Juventus Planet": "🦓 Juventus Planet"}
CANALI_STR = {f"Streaming {i}": f"🖥 Streaming {i}" for i in range(1, 10)}
TUTTI_I_CANALI = {**CANALI_FISSI, **CANALI_STR}

PACCHETTI_INC = {"1k": "50€", "2k": "80€", "5k": "180€", "10k": "330€", "15k": "460€", "20k": "580€", "25k": "690€", "30k": "780€"}

# --- 3. LOGICA PREZZI (Il tuo listino) ---
def calcola_prezzo(u_data):
    sel = u_data.get('sel', [])
    ore = u_data.get('ore', 3)
    tot = 0
    if "Goal" in sel: tot += {3: 5, 6: 7.5, 12: 11, 24: 13.5}.get(ore, 0)
    if "Juventus Planet" in sel: tot += {3: 4, 6: 5.5, 12: 8, 24: 12}.get(ore, 0)
    q_str = len([c for c in sel if "Streaming" in c])
    if q_str > 0:
        if q_str == 9: p = {3: 25, 6: 35, 12: 50, 24: 65}
        elif 5 <= q_str <= 8: p = {3: 20, 6: 30, 12: 40, 24: 50}
        else: p = {3: 6*q_str, 6: 9.5*q_str, 12: 15*q_str, 24: 19.5*q_str}
        tot += p.get(ore, 0)
    if u_data.get('repost'): tot += (3 * len(sel))
    if u_data.get('fissato'): tot += (1 * len(sel))
    return tot

# --- 4. TASTIERE ---
def kb_home(u_id):
    kb = [
        [InlineKeyboardButton("📢 Acquista Sponsor", callback_data="buy_sp")],
        [InlineKeyboardButton("📈 Acquista Incrementi", callback_data="buy_inc")],
        [InlineKeyboardButton("🎁 Stato Ordine", callback_data="st_ord"), InlineKeyboardButton("🆘 Assistenza", callback_data="assist")],
        [InlineKeyboardButton("💰 Listino Prezzi ↗️", url="https://t.me/listinoSoccerHubOff")],
        [InlineKeyboardButton("⚠️ T&C ↗️", callback_data="tc_page"), InlineKeyboardButton("ℹ️ Come Funziona", callback_data="info_how")]
    ]
    if u_id == ADMIN_ID: kb.insert(0, [InlineKeyboardButton("👮‍♂️ PANNELLO ADMIN", callback_data="adm_panel")])
    return InlineKeyboardMarkup(kb)

def kb_canali(sel):
    kb = []
    kb.append([InlineKeyboardButton(f"{'✅ ' if c in sel else ''}{n}", callback_data=f"t_{c}") for c, n in CANALI_FISSI.items()])
    row = []
    for i in range(1, 10):
        cid = f"Streaming {i}"; row.append(InlineKeyboardButton(f"{'✅ ' if cid in sel else ''}Str {i}", callback_data=f"t_{cid}"))
        if len(row) == 3: kb.append(row); row = []
    kb.append([InlineKeyboardButton("✨ Seleziona Tutti", callback_data="all_on"), InlineKeyboardButton("❌ Svuota", callback_data="all_off")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="buy_sp"), InlineKeyboardButton("Avanti ➡️", callback_data="go_ore")])
    return InlineKeyboardMarkup(kb)

# --- 5. GESTORE DEI CLIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_id = update.effective_user.id
    context.user_data.clear()
    txt = "👋 <b>Benvenuto su SoccerHub!</b>\n\n🟢 Il servizio ufficiale per sponsorizzazioni e incremento iscritti.\n\n👇 <b>Scegli il servizio:</b>"
    if update.callback_query: await update.callback_query.edit_message_text(txt, reply_markup=kb_home(u_id), parse_mode='HTML')
    else: await update.message.reply_text(txt, reply_markup=kb_home(u_id), parse_mode='HTML')

async def clic_bottone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = context.user_data
    await q.answer() # Fondamentale per sbloccare il tasto

    if q.data == "back": await start(update, context)

    # Sezioni Informative
    elif q.data == "assist":
        await q.edit_message_text("🆘 <b>ASSISTENZA</b>\n\n👤 Admin: @Calogero7\n🤖 Supporto: @SoccerPassionLimitatibot",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="back")]]), parse_mode='HTML')

    elif q.data == "info_how":
        txt = "⚙️ <b>COME FUNZIONA</b>\n\n1️⃣ Scegli il servizio\n2️⃣ Seleziona canali e durata\n3️⃣ Paga e vai online!"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="back")]]), parse_mode='HTML')

    elif q.data == "tc_page":
        await q.edit_message_text("⚠️ <b>TERMINI E CONDIZIONI</b>\n\nAccetti i termini acquistando il servizio.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="back")]]), parse_mode='HTML')

    # Sponsorizzazione
    elif q.data == "buy_sp":
        kb = [[InlineKeyboardButton("🌐 Canale Standard", callback_data="std")],[InlineKeyboardButton("🏴‍☠️ IPTV/Vendita", callback_data="iptv")],[InlineKeyboardButton("⬅️ Indietro", callback_data="back")]]
        await q.edit_message_text("⚖️ <b>Tipo di contenuto?</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif q.data == "std":
        u['sel'] = u.get('sel', [])
        await q.edit_message_text("👇 <b>Seleziona i canali:</b>", reply_markup=kb_canali(u['sel']), parse_mode='HTML')

    elif q.data.startswith("t_"):
        c = q.data.split("_")[1]
        u['sel'] = u.get('sel', [])
        if c in u['sel']: u['sel'].remove(c)
        else: u['sel'].append(c)
        await q.edit_message_reply_markup(reply_markup=kb_canali(u['sel']))

    elif q.data == "all_on":
        u['sel'] = list(TUTTI_I_CANALI.keys())
        await q.edit_message_reply_markup(reply_markup=kb_canali(u['sel']))

    elif q.data == "go_ore":
        if not u.get('sel'): return
        kb = [[InlineKeyboardButton("3h", callback_data="h_3"), InlineKeyboardButton("6h", callback_data="h_6")],[InlineKeyboardButton("⬅️ Indietro", callback_data="std")]]
        await q.edit_message_text("🕒 <b>Scegli durata:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    # Incrementi
    elif q.data == "buy_inc":
        kb = [[InlineKeyboardButton(f"{k} - {v}", callback_data=f"inc_{k}")] for k,v in PACCHETTI_INC.items()]
        kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back")])
        await q.edit_message_text("📈 <b>Scegli pacchetto:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

# --- 6. SERVER E AVVIO ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Bot Online"

if __name__ == '__main__':
    Thread(target=lambda: webapp.run(host='0.0.0.0', port=10000)).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(clic_bottone))
    app.run_polling()
