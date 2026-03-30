import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
TOKEN = "8601357271:AAEmVAdioTlrZ5nMAwZgOwM7U-ggmp_flL4"
ADMIN_ID = 8361466889

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATI ---
CANALI_STREAMING = [f"Streaming {i}" for i in range(1, 10)]
CANALI_FISSI = ["Goal", "Juventus Planet"]
TUTTI_I_CANALI = CANALI_FISSI + CANALI_STREAMING
PREZZI_INC = {"1K": 50, "2K": 80, "3K": 120, "5K": 200}

def calcola_prezzo(sel, ore):
    tot = 0
    p_fissi = {"Goal": {3: 5, 6: 7.5, 12: 11, 24: 13.5}, "Juventus Planet": {3: 4, 6: 5.5, 12: 8, 24: 12}}
    for c in CANALI_FISSI:
        if c in sel: tot += p_fissi[c].get(ore, 0)
    str_sel = [c for c in sel if "Streaming" in c]
    q = len(str_sel)
    if q > 0:
        if q == 9: p_s = {3: 25, 6: 35, 12: 50, 24: 65}
        elif 5 <= q <= 8: p_s = {3: 20, 6: 30, 12: 40, 24: 50}
        elif 3 <= q <= 4: p_s = {3: 15, 6: 20, 12: 35, 24: 45}
        else: p_s = {3: 6*q, 6: 9.5*q, 12: 15*q, 24: 19.5*q}
        tot += p_s.get(ore, 0)
    return tot

# --- TASTIERE ---
def menu_principale(user_id, force_user_view=False):
    # Mostra l'admin panel se l'id corrisponde e non stiamo forzando la vista utente
    if user_id == ADMIN_ID and not force_user_view:
        kb = [
            [InlineKeyboardButton("📊 Gestisci Ordini", callback_data='admin_orders')],
            [InlineKeyboardButton("🌐 Visita Utente", callback_data='user_view')]
        ]
    else:
        kb = [
            [InlineKeyboardButton("📣 Acquista Sponsor", callback_data='sel_std')],
            [InlineKeyboardButton("📈 Acquista Incrementi", callback_data='menu_inc')],
            [InlineKeyboardButton("🎁 Stato Ordine", callback_data='status'),
             InlineKeyboardButton("🆘 Assistenza", url='https://t.me/GlobalSportsContatto')],
            [InlineKeyboardButton("💰 Listino Prezzi ↗️", url='https://t.me/GlobalSportsSponsor'),
             InlineKeyboardButton("⚠️ T&C ↗️", callback_data='tc')],
            [InlineKeyboardButton("ℹ️ Come Funziona", callback_data='info')]
        ]
    return InlineKeyboardMarkup(kb)

def kb_selezione(sel):
    kb = []
    row_fissi = []
    for c in CANALI_FISSI:
        s = " ✅" if c in sel else ""
        row_fissi.append(InlineKeyboardButton(f"{c}{s}", callback_data=f"t_{c}"))
    kb.append(row_fissi)

    row = []
    for c in CANALI_STREAMING:
        num = c.split()[1]
        s = "✅" if c in sel else num
        row.append(InlineKeyboardButton(f"Str {s}", callback_data=f"t_{c}"))
        if len(row) == 3: kb.append(row); row = []

    kb.append([InlineKeyboardButton("✨ Selezione Tutti", callback_data="all_in")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start"),
               InlineKeyboardButton("Avanti ➡️", callback_data="go_durata")])
    return InlineKeyboardMarkup(kb)

# --- SERVER ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Online"
def run(): webapp.run(host='0.0.0.0', port=10000)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logging.info(f"Utente connesso: {user_id}") # Stampo nei log di Render l'ID per sicurezza
    context.user_data.clear()

    if user_id == ADMIN_ID:
        txt = "👮‍♂️ <b>PANNELLO ADMIN</b>\nScegli un'azione:"
    else:
        txt = (
            "👋 <b>Benvenuto su SoccerHub!</b>\n\n"
            "✅ Il servizio ufficiale per <b>sponsorizzazioni</b> e <b>incremento iscritti</b> sul "
            "nostro network di canali dedicati al calcio.\n\n"
            "👇 <b>Scegli il servizio</b> di cui hai bisogno:"
        )

    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=menu_principale(user_id), parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=menu_principale(user_id), parse_mode='HTML')

async def gestore_messaggi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = context.user_data
    if u_data.get('attesa_orario'):
        u_data['fascia'] = update.message.text
        u_data['attesa_orario'] = False
        txt = (f"✅ <b>RIEPILOGO ORDINE</b>\n\n"
               f"📢 Canali: {len(u_data['sel'])}\n"
               f"📅 Data: {u_data['data']}\n"
               f"🕒 Inizio: {u_data['fascia']}\n"
               f"💰 <b>Totale: {u_data['prezzo']}€</b>")
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ INVIA", callback_data="conf")]]), parse_mode='HTML')

async def gestore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    u_data = context.user_data
    user_id = query.from_user.id
    await query.answer()

    # --- SEZIONE ADMIN ---
    if data == 'admin_orders':
        await query.edit_message_text("📊 <b>Gestione Ordini</b>\nAl momento gestisci gli ordini manualmente dalla chat.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")]]), parse_mode='HTML')

    elif data == 'user_view':
        txt = "👀 <b>VISTA UTENTE (Test)</b>\n\nScegli un'opzione dal menu:"
        await query.edit_message_text(txt, reply_markup=menu_principale(user_id, force_user_view=True), parse_mode='HTML')

    # --- SEZIONE INFO / STATUS ---
    elif data == 'status':
        await query.edit_message_text("🎁 <b>Stato Ordine</b>\n\nNon hai ordini attivi al momento o sono in fase di elaborazione. Per info contatta l'assistenza.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")]]), parse_mode='HTML')

    elif data == 'tc':
        await query.edit_message_text("⚠️ <b>Termini e Condizioni</b>\n\n1. Il pagamento va effettuato anticipatamente.\n2. Gli orari sono indicativi e possono subire lievi variazioni.\n3. Non si accettano rimborsi a lavoro avviato.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")]]), parse_mode='HTML')

    elif data == 'info':
        await query.edit_message_text("ℹ️ <b>Come Funziona</b>\n\n1. Scegli un pacchetto dal menu.\n2. Seleziona canali e orari.\n3. Invia la richiesta.\n4. L'admin ti scriverà per il pagamento in privato.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")]]), parse_mode='HTML')

    # --- FLUSSO SPONSOR ---
    elif data == 'sel_std':
        u_data['sel'] = []
        u_data['tipo'] = "Sponsor"
        await query.edit_message_text("Hai scelto la modalità: 🌐 <b>Canale/Gruppo Standard</b>\n\n🤝 <b>Seleziona i canali</b>:", reply_markup=kb_selezione(u_data['sel']), parse_mode='HTML')

    elif data.startswith('t_'):
        c = data.replace('t_', '')
        if c in u_data['sel']: u_data['sel'].remove(c)
        else: u_data['sel'].append(c)
        await query.edit_message_reply_markup(reply_markup=kb_selezione(u_data['sel']))

    elif data == 'all_in':
        u_data['sel'] = list(TUTTI_I_CANALI)
        await query.edit_message_reply_markup(reply_markup=kb_selezione(u_data['sel']))

    elif data == 'go_durata':
        if not u_data.get('sel') or len(u_data['sel']) == 0:
            return await query.answer("⚠️ Devi selezionare almeno un canale per poter proseguire!", show_alert=True)
        kb = [[InlineKeyboardButton("3.0h", callback_data="h_3"), InlineKeyboardButton("6.0h", callback_data="h_6")],
              [InlineKeyboardButton("12.0h", callback_data="h_12"), InlineKeyboardButton("24.0h", callback_data="h_24")],
              [InlineKeyboardButton("⬅️ Indietro", callback_data="sel_std")]]
        await query.edit_message_text("⏱ <b>Scegli la durata:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data.startswith('h_'):
        u_data['ore'] = float(data.replace('h_', ''))
        u_data['prezzo'] = calcola_prezzo(u_data['sel'], u_data['ore'])
        kb = []
        for i in range(1, 7):
            g = (datetime.now() + timedelta(days=i)).strftime("%d-%m-%Y")
            kb.append([InlineKeyboardButton(f"📅 {g}", callback_data=f"d_{g}")])
        kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="go_durata")])
        await query.edit_message_text("🗓 <b>Seleziona il giorno:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data.startswith('d_'):
        u_data['data'] = data.replace('d_', '')
        kb = [
            [InlineKeyboardButton("09:00", callback_data="f_09:00"), InlineKeyboardButton("12:00", callback_data="f_12:00")],
            [InlineKeyboardButton("15:00", callback_data="f_15:00"), InlineKeyboardButton("18:00", callback_data="f_18:00")],
            [InlineKeyboardButton("21:00", callback_data="f_21:00"), InlineKeyboardButton("23:00", callback_data="f_23:00")],
            [InlineKeyboardButton("✍️ Inserisci Orario Manualmente", callback_data="manual_time")],
            [InlineKeyboardButton("⬅️ Cambia Giorno", callback_data="go_durata")]
        ]
        await query.edit_message_text(f"🗓 <b>GIORNO SCELTO: {u_data['data']}</b>\nScegli l'orario di inizio:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data == "manual_time":
        u_data['attesa_orario'] = True
        await query.edit_message_text("✍️ <b>Inserimento Manuale</b>\nScrivi l'orario desiderato (es: 10:30) in chat.")

    elif data.startswith('f_'):
        u_data['fascia'] = data.replace('f_', '')
        txt = (f"✅ <b>RIEPILOGO ORDINE</b>\n\n"
               f"📢 Canali: {len(u_data['sel'])}\n"
               f"📅 Data: {u_data['data']}\n"
               f"🕒 Inizio: {u_data['fascia']}\n"
               f"💰 <b>Totale: {u_data['prezzo']}€</b>")
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ INVIA", callback_data="conf")]]), parse_mode='HTML')

    # --- FLUSSO INCREMENTI ---
    elif data == 'menu_inc':
        kb = [[InlineKeyboardButton(f"Pacchetto {k} - {v}€", callback_data=f"inc_{k}")] for k, v in PREZZI_INC.items()]
        kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start")])
        await query.edit_message_text("🚀 <b>INCREMENTI</b>\nScegli il pacchetto di iscritti che desideri acquistare:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data.startswith('inc_'):
        p = data.replace('inc_', '')
        u_data['tipo'] = "Incremento"
        u_data['pacco'] = p
        u_data['prezzo'] = PREZZI_INC[p]
        txt = f"🚀 <b>Hai scelto l'incremento:</b> {p}\n💰 <b>Prezzo totale:</b> {u_data['prezzo']}€\n\nPremi su INVIA per inoltrare la richiesta."
        kb = [[InlineKeyboardButton("✅ INVIA", callback_data="conf")], [InlineKeyboardButton("⬅️ Annulla", callback_data="menu_inc")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    # --- CONFERMA FINALE & INVIO ADMIN ---
    elif data == "conf":
        # Formattazione Pulita per l'Admin
        username = query.from_user.username if query.from_user.username else query.from_user.first_name

        if u_data.get('tipo') == "Incremento":
            testo_admin = (f"📈 <b>NUOVO ORDINE (INCREMENTI)!</b>\n\n"
                           f"👤 Da: @{username}\n"
                           f"🚀 Pacchetto: {u_data['pacco']}\n"
                           f"💶 <b>Da Incassare: {u_data['prezzo']}€</b>")
        else:
            lista_canali = "\n- ".join(u_data['sel'])
            testo_admin = (f"📣 <b>NUOVO ORDINE (SPONSOR)!</b>\n\n"
                           f"👤 Da: @{username}\n\n"
                           f"📢 <b>Canali:</b>\n- {lista_canali}\n\n"
                           f"⏱ Durata: {u_data['ore']}h\n"
                           f"📅 Data: {u_data['data']}\n"
                           f"🕒 Fascia: {u_data['fascia']}\n"
                           f"💶 <b>Da Incassare: {u_data['prezzo']}€</b>")

        await context.bot.send_message(ADMIN_ID, testo_admin, parse_mode='HTML')
        await query.edit_message_text("✅ <b>Richiesta inviata con successo!</b>\n\nL'amministratore ha ricevuto i dettagli del tuo ordine e ti contatterà a breve in questa chat per procedere con il pagamento.", parse_mode='HTML')

    # --- NAVIGAZIONE ---
    elif data == 'back_to_start':
        await start(update, context)

if __name__ == '__main__':
    Thread(target=run).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(CallbackQueryHandler(gestore_callback))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gestore_messaggi))
    bot.run_polling()
