import logging, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from flask import Flask
from threading import Thread

# --- 1. CONFIGURAZIONE ---
TOKEN = "8601357271:AAEmVAdioTlrZ5nMAwZgOwM7U-ggmp_flL4"
ADMIN_ID = 8361466889

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- 2. DATI REALI ---
CANALI_FISSI = {"Goal": "⚽️ Goal", "Juventus Planet": "🦓 Juventus Planet"}
CANALI_STR = {f"Streaming {i}": f"🖥 Streaming {i}" for i in range(1, 10)}
TUTTI_I_CANALI = {**CANALI_FISSI, **CANALI_STR}

PACCHETTI_INC = {"1k": "50€", "2k": "80€", "5k": "180€", "10k": "330€", "15k": "460€", "20k": "580€", "25k": "690€", "30k": "780€"}

# --- 3. MOTORE CALCOLO PREZZI ---
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
        elif 3 <= q_str <= 4: p = {3: 15, 6: 20, 12: 35, 24: 45}
        else: p = {3: 6*q_str, 6: 9.5*q_str, 12: 15*q_str, 24: 19.5*q_str}
        tot += p.get(ore, 0)

    if u_data.get('repost'): tot += (3 * len(sel))
    if u_data.get('fissato'): tot += (1 * len(sel))
    return tot

# --- 4. TASTIERE GRAFICHE ---
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
        cid = f"Streaming {i}"
        row.append(InlineKeyboardButton(f"{'✅ ' if cid in sel else ''}Str {i}", callback_data=f"t_{cid}"))
        if len(row) == 3: kb.append(row); row = []
    kb.append([InlineKeyboardButton("✨ Seleziona Tutti", callback_data="all_on"), InlineKeyboardButton("❌ Svuota", callback_data="all_off")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="buy_sp"), InlineKeyboardButton("Avanti ➡️", callback_data="go_ore")])
    return InlineKeyboardMarkup(kb)

def kb_aggiunte(u):
    r_txt = "✅ Repost (+3€)" if u.get('repost') else "❌ Repost (+3€)"
    f_txt = "✅ Fissato (+1€)" if u.get('fissato') else "❌ Fissato (+1€)"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(r_txt, callback_data="agg_r"), InlineKeyboardButton(f_txt, callback_data="agg_f")],
        [InlineKeyboardButton("📅 Procedi al Calendario", callback_data="go_cal")],
        [InlineKeyboardButton("⬅️ Indietro", callback_data="go_ore")]
    ])

# --- 5. GESTIONE COMANDI E BOTTONI ---
async def start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_id = update.effective_user.id
    context.user_data.clear() # Pulisce i dati vecchi
    txt = "👋 <b>Benvenuto su SoccerHub!</b>\n\n🟢 Il servizio ufficiale per sponsorizzazioni e incremento iscritti.\n\n👇 <b>Scegli il servizio di cui hai bisogno:</b>"
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb_home(u_id), parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=kb_home(u_id), parse_mode='HTML')

async def elabora_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data
    u = context.user_data
    try: await q.answer() # Evita che il bottone si "congeli"
    except: pass

    # MENU PRINCIPALE
    if d == "back":
        await start_bot(update, context)

    elif d == "assist":
        txt = "🆘 <b>ASSISTENZA E SUPPORTO</b>\n\n👤 Admin: @Calogero7\n🤖 Supporto: @SoccerPassionLimitatibot"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Torna al Menu", callback_data="back")]]), parse_mode='HTML')

    elif d == "tc_page":
        txt = "⚠️ <b>TERMINI E CONDIZIONI</b>\n\n1️⃣ Non accettiamo contenuti illegali.\n2️⃣ Servizio parte dopo il pagamento.\n3️⃣ Nessun rimborso a lavoro avviato."
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Torna al Menu", callback_data="back")]]), parse_mode='HTML')

    elif d == "info_how":
        txt = "⚙️ <b>COME FUNZIONA IL BOT</b>\n\n1️⃣ Scegli il servizio\n2️⃣ Seleziona canali e durata\n3️⃣ Inoltra il post o aggiungi il bot per l'incremento\n4️⃣ Paga e vai online!"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Torna al Menu", callback_data="back")]]), parse_mode='HTML')

    elif d == "st_ord":
        txt = "📄 <b>STATO DEL TUO ORDINE</b>\n\n🟡 Nessuna procedura in corso."
        if u.get('state') == 'WAIT_FORWARD': txt = "📄 <b>STATO DEL TUO ORDINE</b>\n\n⌛️ <b>Hai una procedura in corso:</b> In attesa del materiale."
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Torna al Menu", callback_data="back")]]), parse_mode='HTML')

    elif d == "adm_panel":
        await q.edit_message_text("👮‍♂️ <b>PANNELLO ADMIN</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="back")]]), parse_mode='HTML')

    # INCREMENTI
    elif d == "buy_inc":
        kb = []
        keys = list(PACCHETTI_INC.keys())
        for i in range(0, len(keys), 2):
            kb.append([InlineKeyboardButton(f"🔹 {k} ⇨ {PACCHETTI_INC[k]}", callback_data=f"inc_{k}") for k in keys[i:i+2]])
        kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back")])
        await q.edit_message_text("📈 <b>INCREMENTI ISCRITTI</b>\nScegli il pacchetto desiderato:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif d.startswith("inc_"):
        pacc = d.split("_")[1]
        u['state'] = 'WAIT_FORWARD'
        txt = f"<b>Pacchetto:</b> {pacc} iscritti ({PACCHETTI_INC[pacc]})\n\n🛠 <b>ISTRUZIONI:</b>\n1️⃣ Aggiungi @SPStreamingbot come Amministratore.\n2️⃣ INOLTRA QUI un messaggio dal tuo canale."
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Annulla", callback_data="buy_inc")]]), parse_mode='HTML')

    # SPONSOR
    elif d == "buy_sp":
        kb = [[InlineKeyboardButton("🌐 Canale Standard", callback_data="std")],[InlineKeyboardButton("🏴‍☠️ IPTV/Vendita Account", callback_data="iptv")],[InlineKeyboardButton("⬅️ Indietro", callback_data="back")]]
        await q.edit_message_text("⚖️ <b>Che tipo di contenuto vuoi sponsorizzare?</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif d == "iptv":
        await q.answer("Sezione IPTV in aggiornamento!", show_alert=True)

    elif d == "std":
        if 'sel' not in u: u['sel'] = []
        await q.edit_message_text("👇 <b>Seleziona i canali:</b>", reply_markup=kb_canali(u['sel']), parse_mode='HTML')

    elif d.startswith("t_"):
        c = d.replace("t_", "")
        if 'sel' not in u: u['sel'] = []
        if c in u['sel']: u['sel'].remove(c)
        else: u['sel'].append(c)
        await q.edit_message_reply_markup(reply_markup=kb_canali(u['sel']))

    elif d == "all_on":
        u['sel'] = list(TUTTI_I_CANALI.keys())
        await q.edit_message_reply_markup(reply_markup=kb_canali(u['sel']))

    elif d == "all_off":
        u['sel'] = []
        await q.edit_message_reply_markup(reply_markup=kb_canali(u['sel']))

    elif d == "go_ore":
        if not u.get('sel'): return await q.answer("⚠️ Seleziona almeno un canale!", show_alert=True)
        kb = [[InlineKeyboardButton("3 Ore", callback_data="h_3"), InlineKeyboardButton("6 Ore", callback_data="h_6")],
              [InlineKeyboardButton("12 Ore", callback_data="h_12"), InlineKeyboardButton("24 Ore", callback_data="h_24")],
              [InlineKeyboardButton("⬅️ Indietro", callback_data="std")]]
        await q.edit_message_text("🕒 <b>SCELTA ORE</b>\nScegli la durata:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif d.startswith("h_"):
        u['ore'] = int(d.split("_")[1])
        u['repost'] = u.get('repost', False)
        u['fissato'] = u.get('fissato', False)
        await q.edit_message_text(f"➕ <b>AGGIUNTE</b>\nDurata: {u['ore']}h", reply_markup=kb_aggiunte(u), parse_mode='HTML')

    elif d == "agg_r":
        u['repost'] = not u.get('repost')
        await q.edit_message_reply_markup(reply_markup=kb_aggiunte(u))

    elif d == "agg_f":
        u['fissato'] = not u.get('fissato')
        await q.edit_message_reply_markup(reply_markup=kb_aggiunte(u))

    elif d == "go_cal":
        kb = [[InlineKeyboardButton("Oggi", callback_data="cal_1"), InlineKeyboardButton("Domani", callback_data="cal_2")], [InlineKeyboardButton("⬅️ Indietro", callback_data="go_ore")]]
        await q.edit_message_text("🗓 <b>CALENDARIO</b>\nScegli il giorno:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif d.startswith("cal_"):
        kb = [[InlineKeyboardButton("18:00", callback_data="time_18"), InlineKeyboardButton("21:00", callback_data="time_21")], [InlineKeyboardButton("⬅️ Indietro", callback_data="go_cal")]]
        await q.edit_message_text("⏰ <b>ORARIO</b>\nScegli l'orario:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif d.startswith("time_"):
        costo = calcola_prezzo(u)
        txt = f"🛒 <b>IL TUO CARRELLO FINALE</b>\n\n📢 Canali: {len(u['sel'])}\n⏱ Durata: {u['ore']}h\n💰 <b>Totale da pagare: {costo:.2f}€</b>\n\nInoltra il post che vuoi sponsorizzare in questa chat!"
        u['state'] = 'WAIT_POST'
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Annulla Ordine", callback_data="back")]]), parse_mode='HTML')

# Riconosce i messaggi inoltrati o inviati per gli ordini
async def ricevi_messaggi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = context.user_data
    if u.get('state') == 'WAIT_FORWARD' and update.message.forward_from_chat:
        await update.message.reply_text("✅ Canale rilevato con successo! L'amministratore elaborerà la tua richiesta.")
        u['state'] = None
    elif u.get('state') == 'WAIT_POST':
        await update.message.reply_text("✅ Post ricevuto nel sistema! Attendi conferma.")
        u['state'] = None

# --- SERVER WEB (Render) ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Bot Attivo e Funzionante!"

if __name__ == '__main__':
    Thread(target=lambda: webapp.run(host='0.0.0.0', port=10000)).start()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start_bot))
    app.add_handler(CallbackQueryHandler(elabora_click))
    app.add_handler(MessageHandler(filters.ALL, ricevi_messaggi))

    app.run_polling()
