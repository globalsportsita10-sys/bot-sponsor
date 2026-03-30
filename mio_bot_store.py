import logging
import calendar
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

def calcola_prezzo(u_data):
    sel = u_data.get('sel', [])
    ore = u_data.get('ore', 3)
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

    # Aggiunte (costo applicato ad ogni singolo canale)
    num_canali = len(sel)
    if u_data.get('repost'): tot += (3 * num_canali)
    if u_data.get('fissato'): tot += (1 * num_canali)

    return tot

# --- TASTIERE ---
def menu_principale(user_id, force_user_view=False):
    if user_id == ADMIN_ID and not force_user_view:
        kb = [[InlineKeyboardButton("📊 Gestisci Ordini", callback_data='admin_orders')],
              [InlineKeyboardButton("🌐 Visita Utente", callback_data='user_view')]]
    else:
        kb = [[InlineKeyboardButton("📣 Acquista Sponsor", callback_data='sel_std')],
              [InlineKeyboardButton("📈 Acquista Incrementi", callback_data='menu_inc')],
              [InlineKeyboardButton("🎁 Stato Ordine", callback_data='status'), InlineKeyboardButton("🆘 Assistenza", url='https://t.me/GlobalSportsContatto')],
              [InlineKeyboardButton("💰 Listino Prezzi ↗️", url='https://t.me/GlobalSportsSponsor'), InlineKeyboardButton("⚠️ T&C ↗️", callback_data='tc')],
              [InlineKeyboardButton("ℹ️ Come Funziona", callback_data='info')]]
    return InlineKeyboardMarkup(kb)

def kb_aggiunte(u_data):
    # Simboli e logica come da screenshot
    r_status = "✅" if u_data.get('repost') else "❌"
    f_status = "✅" if u_data.get('fissato') else "❌"
    kb = [
        [InlineKeyboardButton(f"{r_status} Repost (+3€)", callback_data="toggle_repost")],
        [InlineKeyboardButton(f"{f_status} Fissato (+1€)", callback_data="toggle_fissato")],
        [InlineKeyboardButton("🗓 Procedi al Calendario", callback_data="go_calendar")],
        [InlineKeyboardButton("⬅️ Indietro", callback_data="go_durata")]
    ]
    return InlineKeyboardMarkup(kb)

def kb_selezione(sel):
    kb = []
    row_fissi = [InlineKeyboardButton(f"{c}{' ✅' if c in sel else ''}", callback_data=f"t_{c}") for c in CANALI_FISSI]
    kb.append(row_fissi)
    row = []
    for c in CANALI_STREAMING:
        num = c.split()[1]
        row.append(InlineKeyboardButton(f"Str {'✅' if c in sel else num}", callback_data=f"t_{c}"))
        if len(row) == 3: kb.append(row); row = []
    kb.append([InlineKeyboardButton("✨ Selezione Tutti", callback_data="all_in")])
    kb.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_start"), InlineKeyboardButton("Avanti ➡️", callback_data="go_durata")])
    return InlineKeyboardMarkup(kb)

# --- SERVER ---
webapp = Flask('')
@webapp.route('/')
def home(): return "Online"
def run(): webapp.run(host='0.0.0.0', port=10000)

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    txt = "👮‍♂️ <b>PANNELLO ADMIN</b>" if user_id == ADMIN_ID else "👋 <b>Benvenuto su SoccerHub!</b>"
    reply_markup = menu_principale(user_id)
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_text(txt, reply_markup=reply_markup, parse_mode='HTML')

async def gestore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    u_data = context.user_data
    await query.answer()

    if data == 'sel_std':
        u_data['sel'] = []
        await query.edit_message_text("🤝 <b>Seleziona i canali:</b>", reply_markup=kb_selezione(u_data['sel']), parse_mode='HTML')

    elif data.startswith('t_'):
        c = data.replace('t_', '')
        if c in u_data['sel']: u_data['sel'].remove(c)
        else: u_data['sel'].append(c)
        await query.edit_message_reply_markup(reply_markup=kb_selezione(u_data['sel']))

    elif data == 'all_in':
        u_data['sel'] = list(TUTTI_I_CANALI)
        await query.edit_message_reply_markup(reply_markup=kb_selezione(u_data['sel']))

    elif data == 'go_durata':
        if not u_data.get('sel'): return await query.answer("⚠️ Seleziona almeno un canale!", show_alert=True)
        kb = [[InlineKeyboardButton("3.0h", callback_data="h_3"), InlineKeyboardButton("6.0h", callback_data="h_6")],
              [InlineKeyboardButton("12.0h", callback_data="h_12"), InlineKeyboardButton("24.0h", callback_data="h_24")],
              [InlineKeyboardButton("⬅️ Indietro", callback_data="sel_std")]]
        await query.edit_message_text("⏱ <b>Scegli la durata:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    # --- SEZIONE AGGIUNTE ---
    elif data.startswith('h_'):
        u_data['ore'] = float(data.replace('h_', ''))
        u_data['repost'] = False
        u_data['fissato'] = False
        txt = f"➕ <b>AGGIUNTE</b>\n\n🕒 Durata: {u_data['ore']}h.\n\nSeleziona le aggiunte (<i>il costo si applica ad ogni singolo canale</i>):"
        await query.edit_message_text(txt, reply_markup=kb_aggiunte(u_data), parse_mode='HTML')

    elif data == "toggle_repost":
        u_data['repost'] = not u_data.get('repost', False)
        await query.edit_message_reply_markup(reply_markup=kb_aggiunte(u_data))

    elif data == "toggle_fissato":
        u_data['fissato'] = not u_data.get('fissato', False)
        await query.edit_message_reply_markup(reply_markup=kb_aggiunte(u_data))

    # --- CALENDARIO ---
    elif data == "go_calendar":
        oggi = datetime.now()
        ultimo_giorno = calendar.monthrange(oggi.year, oggi.month)[1]
        u_data['prezzo'] = calcola_prezzo(u_data)

        aggiunte_str = []
        if u_data.get('repost'): aggiunte_str.append("Repost")
        if u_data.get('fissato'): aggiunte_str.append("Fissato")
        agg_txt = ", ".join(aggiunte_str) if aggiunte_str else "Nessuna"

        txt = f"📅 <b>CALENDARIO</b> (<i>{oggi.strftime('%d/%m')} - {ultimo_giorno}/{oggi.month:02d}</i>)\n\n"
        txt += f"⏱ Durata: {u_data['ore']}h\n➕ Aggiunte: {agg_txt}\n\n"
        txt += "Scegli il <b>giorno</b> in cui vuoi essere sponsorizzato:"

        kb = []
        row = []
        for giorno in range(oggi.day, ultimo_giorno + 1):
            data_str = f"{giorno:02d}-{oggi.month:02d}-{oggi.year}"
            label = f"🚫 {giorno:02d}/{oggi.month:02d}" if giorno == oggi.day else f"{giorno:02d}/{oggi.month:02d}"
            callback = "ignore" if giorno == oggi.day else f"d_{data_str}"
            row.append(InlineKeyboardButton(label, callback_data=callback))
            if len(row) == 3: kb.append(row); row = []
        if row: kb.append(row)
        kb.append([InlineKeyboardButton("Successivi ➡️", callback_data="ignore")])
        kb.append([InlineKeyboardButton("⬅️ Torna alle Aggiunte", callback_data=f"h_{u_data['ore']}")])
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data.startswith('d_'):
        u_data['data'] = data.replace('d_', '')
        kb = [[InlineKeyboardButton("09:00", callback_data="f_09:00"), InlineKeyboardButton("12:00", callback_data="f_12:00")],
              [InlineKeyboardButton("15:00", callback_data="f_15:00"), InlineKeyboardButton("18:00", callback_data="f_18:00")],
              [InlineKeyboardButton("21:00", callback_data="f_21:00"), InlineKeyboardButton("23:00", callback_data="f_23:00")],
              [InlineKeyboardButton("✍️ Manuale", callback_data="manual_time")],
              [InlineKeyboardButton("⬅️ Cambia Giorno", callback_data="go_calendar")]]
        await query.edit_message_text(f"📅 <b>GIORNO SCELTO: {u_data['data']}</b>\n\nScegli l'orario di inizio:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='HTML')

    elif data.startswith('f_'):
        u_data['fascia'] = data.replace('f_', '')
        u_data['prezzo'] = calcola_prezzo(u_data)
        agg_txt = ("Repost" if u_data.get('repost') else "") + (" + Fissato" if u_data.get('fissato') else "")
        txt = f"✅ <b>RIEPILOGO</b>\n\n📢 Canali: {len(u_data['sel'])}\n⏱ Durata: {u_data['ore']}h\n➕ Aggiunte: {agg_txt or 'Nessuna'}\n📅 Data: {u_data['data']}\n🕒 Inizio: {u_data['fascia']}\n💰 <b>Totale: {u_data['prezzo']}€</b>"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ INVIA", callback_data="conf")]]), parse_mode='HTML')

    elif data == "conf":
        username = query.from_user.username or query.from_user.first_name
        agg_txt = ("Repost" if u_data.get('repost') else "") + (" + Fissato" if u_data.get('fissato') else "")
        testo_admin = f"📣 <b>ORDINE!</b>\n👤 @{username}\n📢 Canali: {len(u_data['sel'])}\n➕ Aggiunte: {agg_txt or 'Nessuna'}\n📅 Data: {u_data['data']}\n🕒 Fascia: {u_data['fascia']}\n💶 <b>{u_data['prezzo']}€</b>"
        await context.bot.send_message(ADMIN_ID, testo_admin, parse_mode='HTML')
        await query.edit_message_text("✅ Richiesta inviata!", parse_mode='HTML')

    elif data == 'back_to_start': await start(update, context)
    elif data == 'user_view': await query.edit_message_text("👀 VISTA UTENTE", reply_markup=menu_principale(user_id, True), parse_mode='HTML')

if __name__ == '__main__':
    Thread(target=run).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler('start', start))
    bot.add_handler(CallbackQueryHandler(gestore_callback))
    bot.run_polling()
