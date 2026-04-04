import asyncio
import sqlite3
import psycopg2
import random
import string
import logging
import os
from threading import Thread
from flask import Flask
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage

# --- CONFIGURAZIONE SERVER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Attivo"
def run_flask():
   port = int(os.environ.get("PORT", 10000))
   app.run(host='0.0.0.0', port=port)

API_TOKEN = '8513979649:AAEKT-ZT4cA9IhMtjaBFBzsNS_9a2sMGNkw'
ADMIN_ID = 8361466889 # Inserisci il tuo ID
IBAN_DATI = "IT73I0366901600873056346787"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- DATABASE E LOGICA INTERVALLI ---
def init_db():
   conn = sqlite3.connect('ads_booking.db')
   c = conn.cursor()
   c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)')
   c.execute('CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, info TEXT, date TEXT, start_t TEXT, end_t TEXT, causale TEXT, status TEXT)')
   conn.commit()
   conn.close()

def get_booked_intervals():
   conn = sqlite3.connect('ads_booking.db')
   c = conn.cursor()
   c.execute("SELECT date, start_t, info FROM bookings WHERE status = 'APPROVATO' AND type = 'Sponsor'")
   res = c.fetchall()
   conn.close()

   intervals = []
   year = datetime.now().year
   for date_str, start_t, info in res:
       try:
           dur_str = info.split(',')[-1].replace('h', '').strip()
           dur_h = int(dur_str)
       except:
           dur_h = 3 # fallback

       try:
           b_start = datetime.strptime(f"{date_str}/{year} {start_t}", "%d/%m/%Y %H:%M")
           if b_start < datetime.now() - timedelta(days=60):
               b_start = b_start.replace(year=year+1)
           b_end = b_start + timedelta(hours=dur_h)
           intervals.append((b_start, b_end))
       except:
           pass
   return intervals

def is_day_full(date_str):
   conn = sqlite3.connect('ads_booking.db')
   c = conn.cursor()
   c.execute("SELECT id FROM bookings WHERE date = ? AND status = 'APPROVATO' AND type = 'Sponsor'", (date_str,))
   res = c.fetchall()
   conn.close()

   # Regola delle 2 prenotazioni massime
   if len(res) >= 2: return True

   intervals = get_booked_intervals()
   year = datetime.now().year

   # Controlliamo solo gli orari "diurni" principali. Se questi sono tutti sovrapposti,
   # la giornata è considerata "piena" (es. una 12h dalle 09:00 li copre tutti).
   times = ["09:00", "12:00", "15:00", "18:00"]

   for t in times:
       try:
           start_dt = datetime.strptime(f"{date_str}/{year} {t}", "%d/%m/%Y %H:%M")
           if start_dt < datetime.now() - timedelta(days=60):
               start_dt = start_dt.replace(year=year+1)
           end_dt = start_dt + timedelta(hours=3) # Verifica spazio per almeno 3 ore

           overlap = False
           for b_start, b_end in intervals:
               if start_dt < b_end and end_dt > b_start:
                   overlap = True
                   break

           if not overlap:
               return False # C'è almeno uno slot libero!
       except:
           pass

   return True # Tutti gli slot principali sono occupati

init_db()

# --- DATI E PREZZI ---
CHANNELS = {
   "goal": "📹 Goal", "juve": "JuvePlanet ",
   "str_1": "🖥️ Streaming 1", "str_2": "🖥️ Streaming 2", "str_3": "🖥️ Streaming 3",
   "str_4": "🖥️ Streaming 4", "str_5": "🖥️ Streaming 5", "str_6": "🖥️ Streaming 6",
   "str_7": "🖥️ Streaming 7", "str_8": "🖥️ Streaming 8", "str_9": "🖥️ Streaming 9"
}

INCREMENT_PACKAGES = {
   "1K": "🔷 1K - 50€", "2K": "🔷 2K - 80€",
   "3K": "🔶 3K - 120€", "5K": "🔶 5K - 200€"
}

class Flow(StatesGroup):
   channels = State()
   duration = State()
   custom_duration = State()
   extras = State()
   date = State()
   time = State()
   custom_time = State()
   receipt_sponsor = State()
   inc_package = State()
   inc_link = State()
   inc_receipt = State()

def calculate_price(channels, h):
   if h < 3 or h > 24: return 0.0

   def calc_tier(h, t3, t6, t12, t24):
       if h == 3: return t3
       elif h < 6: return t3 + (h-3)*0.25
       elif h == 6: return t6
       elif h < 12: return t6 + (h-6)*0.25
       elif h == 12: return t12
       elif h < 24: return t12 + (h-12)*0.25
       else: return t24

   tot = 0.0
   if "juve" in channels: tot += calc_tier(h, 4.0, 6.0, 9.0, 14.0)
   if "goal" in channels: tot += calc_tier(h, 4.5, 7.0, 11.0, 14.0)

   st_count = sum(1 for c in channels if c.startswith("str_"))
   if st_count == 9: tot += calc_tier(h, 6.5, 11.5, 19.5, 28.0)
   elif st_count > 0: tot += calc_tier(h, 4.5, 8.0, 14.0, 20.0)
   return tot

# --- MENU PRINCIPALE E ADMIN ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
   await state.clear()
   conn = sqlite3.connect('ads_booking.db')
   conn.execute("INSERT OR IGNORE INTO users VALUES (?,?)", (message.from_user.id, message.from_user.username))
   conn.commit(); conn.close()
   if message.from_user.id == ADMIN_ID: await admin_panel(message)
   else: await main_menu(message)

async def admin_panel(obj):
   kb = InlineKeyboardBuilder()
   kb.row(types.InlineKeyboardButton(text="📅 Prenotazioni", callback_data="adm_list"))
   kb.row(types.InlineKeyboardButton(text="🏠 Menu Utente", callback_data="back_main"))
   txt = "👮‍♂️ <b>PANNELLO ADMIN</b>"
   if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=kb.as_markup())
   else: await obj.message.edit_text(txt, reply_markup=kb.as_markup(), parse_mode="HTML")

async def main_menu(obj):
   kb = InlineKeyboardBuilder()
   kb.row(types.InlineKeyboardButton(text="📣 Acquista Sponsor", callback_data="buy_sponsor"))
   kb.row(types.InlineKeyboardButton(text="📈 Acquista Incrementi", callback_data="buy_increment"))
   kb.row(types.InlineKeyboardButton(text="🔍 Stato Ordine", callback_data="order_status"),
          types.InlineKeyboardButton(text="🆘 Assistenza", url="https://t.me/GlobalSportsContatto"))
   kb.row(types.InlineKeyboardButton(text="💰 Listino Prezzi", url="https://t.me/GlobalSportsSponsor"))
   kb.row(types.InlineKeyboardButton(text="⚙️ Come Funziona", callback_data="how_works"))

   txt = """👋 <b>Benvenuto su GlobalSport ADS!</b>\n\n ✅ Il servizio ufficiale del Network per sponsorizzazioni
   e incrementi per i tuoi canali/gruppi.\n\n 👇 Scegli il servizio di cui hai bisogno:"""
   if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=kb.as_markup())
   else: await obj.message.edit_text(txt, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "back_main")
async def back_main(callback: types.CallbackQuery, state: FSMContext):
   await state.clear()
   if callback.from_user.id == ADMIN_ID: await admin_panel(callback)
   else: await main_menu(callback)

@dp.callback_query(F.data == "how_works")
async def how_works(callback: types.CallbackQuery):
   txt = ("⚙️ **Come Funziona**\n\n"
          "1️⃣ <b>Sponsor:</b> Scegli i canali, la durata (fissa o personalizzata), eventuali extra e poi seleziona la data e l'orario in base alle disponibilità.\n"
          "2️⃣ <b>Incrementi:</b> Scegli il pacchetto desiderato, aggiungi il nostro bot come admin al tuo canale con i permessi richiesti e invia il link.\n"
          "3️⃣ <b>Pagamento:</b> Per entrambi i servizi, ti verrà fornito un IBAN e una CAUSALE univoca. Invia lo screen e attendi l'approvazione dell'admin!")
   await callback.message.edit_text(txt, reply_markup=InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main")).as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "order_status")
async def order_status(callback: types.CallbackQuery):
   conn = sqlite3.connect('ads_booking.db')
   c = conn.cursor()
   c.execute("SELECT type, info, date, start_t, status FROM bookings WHERE user_id = ? ORDER BY id DESC LIMIT 5", (callback.from_user.id,))
   rows = c.fetchall()
   conn.close()
   if not rows: txt = "🔍 Nessun ordine in corso."
   else: txt = "🔍 <b>I TUOI ULTIMI ORDINI:</b>\n\n" + "\n\n".join([f"📦 {r[0]} ({r[1]})\n📅 {r[2]} ore {r[3]}\nStato: {r[4]}" for r in rows])
   await callback.message.edit_text(txt, reply_markup=InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main")).as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "adm_list")
async def adm_list(callback: types.CallbackQuery):
   conn = sqlite3.connect('ads_booking.db')
   rows = conn.execute("SELECT user_id, type, date, start_t, end_t FROM bookings WHERE status = 'APPROVATO' ORDER BY id DESC LIMIT 15").fetchall()
   conn.close()
   txt = "📅 <b>PRENOTAZIONI APPROVATE:</b>\n\n" + "\n".join([f"👤 {r[0]} | {r[1]} | {r[2]} ({r[3]}-{r[4]})" for r in rows])
   await callback.message.edit_text(txt, reply_markup=InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main")).as_markup(), parse_mode="HTML")

# --- FLUSSO SPONSOR ---
@dp.callback_query(F.data == "buy_sponsor")
async def buy_sponsor(callback: types.CallbackQuery, state: FSMContext):
   await state.update_data(channels=[], ext_repost=False, ext_fiss=False, ext_nopost=0, cal_page=0)
   await render_channels(callback, [])

async def render_channels(callback, sel):
   kb = InlineKeyboardBuilder()
   for k, v in CHANNELS.items():
       kb.add(types.InlineKeyboardButton(text=f"{v} {'✅' if k in sel else ''}", callback_data=f"ch_{k}"))
   kb.adjust(2)
   if len(sel) == len(CHANNELS): kb.row(types.InlineKeyboardButton(text="❌ Deseleziona Tutti", callback_data="ch_none"))
   else: kb.row(types.InlineKeyboardButton(text="✅ Seleziona Tutti", callback_data="ch_all"))
   kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_dur"))
   await callback.message.edit_text("""👇 <b>Seleziona i canali</b> su cui desideri essere sponsorizzato:
   <i>(Puoi selezionarne anche più di uno.)</i>""", reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("ch_"))
async def handle_channels(callback: types.CallbackQuery, state: FSMContext):
   data = await state.get_data()
   sel = data.get('channels', [])
   c = callback.data.replace("ch_", "")
   if c == "all": sel = list(CHANNELS.keys())
   elif c == "none": sel = []
   elif c in sel: sel.remove(c)
   else: sel.append(c)
   await state.update_data(channels=sel)
   await render_channels(callback, sel)

@dp.callback_query(F.data == "go_dur")
async def go_dur(callback: types.CallbackQuery, state: FSMContext):
   data = await state.get_data()
   if not data.get('channels', []):
       await callback.answer("⚠️ ATTENZIONE: Devi selezionare almeno un canale!", show_alert=True)
       return
   kb = InlineKeyboardBuilder()
   kb.row(types.InlineKeyboardButton(text="3 Ore", callback_data="dur_3"), types.InlineKeyboardButton(text="6 Ore", callback_data="dur_6"))
   kb.row(types.InlineKeyboardButton(text="12 Ore", callback_data="dur_12"), types.InlineKeyboardButton(text="24 Ore", callback_data="dur_24"))
   kb.row(types.InlineKeyboardButton(text="✍️ Scegli durata personalizzata", callback_data="custom_dur"))
   kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="buy_sponsor"))
   await callback.message.edit_text("⏱️ <b>SCELTA ORE</b>\n\n ➕ <b>Scegli</b> la durata della sponsorizzazione o <b>digitalo</b> tu", reply_markup=kb.as_markup(), parse_mode="HTML")
   await state.set_state(Flow.duration)

@dp.callback_query(Flow.duration, F.data == "custom_dur")
async def custom_dur_prompt(callback: types.CallbackQuery, state: FSMContext):
   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="❌ Annulla", callback_data="go_dur"))
   await callback.message.edit_text("""✍️ <b>DURATA PERSONALIZZATA</b>\n\n Scrivi il numero di ore che desideri (minimo 3, massimo 24).
                                    <b>SONO CONSENTITE SOLO ORE INTERE</b>\n\n Esempio:
                                    ⚫ Scrivi '4' per 4 ore""", reply_markup=kb.as_markup(), parse_mode="HTML")
   await state.set_state(Flow.custom_duration)

@dp.message(Flow.custom_duration)
async def custom_dur_input(message: types.Message, state: FSMContext):
   try:
       h = int(message.text)
       if h < 3 or h > 24: raise ValueError
       await state.update_data(duration=h)
       await render_extras(message, state)
   except:
       await message.answer("⚠️ Inserisci un numero valido tra 3 e 24.")

@dp.callback_query(Flow.duration, F.data.startswith("dur_"))
async def handle_dur(callback: types.CallbackQuery, state: FSMContext):
   await state.update_data(duration=int(callback.data.replace("dur_", "")))
   await render_extras(callback, state)

async def render_extras(obj, state):
   data = await state.get_data()
   rep = data.get('ext_repost', False)
   fiss = data.get('ext_fiss', False)
   nop = data.get('ext_nopost', 0)

   kb = InlineKeyboardBuilder()
   kb.row(types.InlineKeyboardButton(text=f"{'✅' if rep else '❌'} Repost (+3€)", callback_data="ex_repost"))
   kb.row(types.InlineKeyboardButton(text=f"{'✅' if fiss else '❌'} Fissato (+1€)", callback_data="ex_fissato"))
   kb.row(types.InlineKeyboardButton(text=f"No-Post (+1€/h) {nop}/3", callback_data="ex_nopost"))
   kb.row(types.InlineKeyboardButton(text="📅 Procedi con la data", callback_data="go_date"))
   kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="go_dur"))

   txt = "➕ <b>AGGIUNTE</b>\n\n Seleziona le aggiunte che preferisci <i>(il costo si applicherà ad ogni singolo canale)</i>"
   if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=kb.as_markup())
   else: await obj.message.edit_text(txt, reply_markup=kb.as_markup(), parse_mode="HTML")
   await state.set_state(Flow.extras)

@dp.callback_query(Flow.extras, F.data.startswith("ex_"))
async def handle_extras(callback: types.CallbackQuery, state: FSMContext):
   data = await state.get_data()
   v = callback.data.replace("ex_", "")
   if v == "repost": await state.update_data(ext_repost=not data.get('ext_repost'))
   elif v == "fissato": await state.update_data(ext_fiss=not data.get('ext_fiss'))
   elif v == "nopost":
       n = data.get('ext_nopost', 0) + 1
       if n > 3: n = 0
       await state.update_data(ext_nopost=n)
   await render_extras(callback, state)

@dp.callback_query(F.data == "go_date")
@dp.callback_query(Flow.extras, F.data == "go_date")
async def render_calendar(callback: types.CallbackQuery, state: FSMContext):
   data = await state.get_data()
   page = data.get('cal_page', 0)

   kb = InlineKeyboardBuilder()
   start_idx = page * 9
   for i in range(start_idx, start_idx + 9):
       d_str = (datetime.now() + timedelta(days=i)).strftime("%d/%m")
       if is_day_full(d_str): kb.add(types.InlineKeyboardButton(text=f"🚫 {d_str}", callback_data="day_full"))
       else: kb.add(types.InlineKeyboardButton(text=d_str, callback_data=f"dt_{d_str}"))
   kb.adjust(3)

   nav_row = []
   if page > 0: nav_row.append(types.InlineKeyboardButton(text="⬅️ Precedenti", callback_data="cal_prev"))
   if page < 2: nav_row.append(types.InlineKeyboardButton(text="Successivi ➡️", callback_data="cal_next"))
   if nav_row: kb.row(*nav_row)

   kb.row(types.InlineKeyboardButton(text="🔙 Torna alle opzioni", callback_data="back_to_extras"))
   await callback.message.edit_text("📅 <b>CALENDARIO</b>\n\n Scegli il <b>giorno</b> in cui preferisci essere <b>sponsorizzato</b>:", reply_markup=kb.as_markup(), parse_mode="HTML")
   await state.set_state(Flow.date)

@dp.callback_query(Flow.date, F.data == "day_full")
async def handle_full(callback: types.CallbackQuery):
   await callback.answer("Giorno pieno! Scegli un'altra data.", show_alert=True)

@dp.callback_query(Flow.date, F.data == "cal_prev")
async def cal_prev(callback: types.CallbackQuery, state: FSMContext):
   d = await state.get_data(); await state.update_data(cal_page=max(0, d.get('cal_page', 0)-1)); await render_calendar(callback, state)

@dp.callback_query(Flow.date, F.data == "cal_next")
async def cal_next(callback: types.CallbackQuery, state: FSMContext):
   d = await state.get_data(); await state.update_data(cal_page=min(2, d.get('cal_page', 0)+1)); await render_calendar(callback, state)

@dp.callback_query(F.data == "back_to_extras")
async def back_to_extras(callback: types.CallbackQuery, state: FSMContext):
   await render_extras(callback, state)

@dp.callback_query(Flow.date, F.data.startswith("dt_"))
async def render_times(callback: types.CallbackQuery, state: FSMContext):
   sel_date = callback.data.replace("dt_", "")
   await state.update_data(date=sel_date)
   data = await state.get_data()
   dur_h = data.get('duration')

   intervals = get_booked_intervals()

   # Crea elenco delle disponibilità occupate
   busy_list = []
   for b_start, b_end in intervals:
       if b_start.strftime("%d/%m") == sel_date:
           busy_list.append(f"• {b_start.strftime('%H:%M')} - {b_end.strftime('%H:%M')} (🚫)")
   busy_text = "\n".join(busy_list) if busy_list else "Tutta la giornata è libera!"

   kb = InlineKeyboardBuilder()
   times = ["09:00", "12:00", "15:00", "18:00", "21:00", "23:00"]
   valid_times = []

   year = datetime.now().year
   for t in times:
       try:
           start_dt = datetime.strptime(f"{sel_date}/{year} {t}", "%d/%m/%Y %H:%M")
           if start_dt < datetime.now() - timedelta(days=60):
               start_dt = start_dt.replace(year=year+1)
           end_dt = start_dt + timedelta(hours=dur_h)

           overlap = False
           for b_start, b_end in intervals:
               if start_dt < b_end and end_dt > b_start:
                   overlap = True
                   break

           if not overlap:
               valid_times.append(t)
       except:
           valid_times.append(t)

   for t in valid_times: kb.add(types.InlineKeyboardButton(text=t, callback_data=f"tm_{t}"))
   kb.adjust(2)

   kb.row(types.InlineKeyboardButton(text="✍️ Inserisci orario personalizzato", callback_data="custom_time"))
   kb.row(types.InlineKeyboardButton(text="⬅️ Cambia giorno", callback_data="go_date"))

   txt = (f"📅 <b>ORARI DISPONIBILI PER IL: <code>{sel_date}</code></b>:\n"
          f"{busy_text}\n\n"
          f"⏰ **Seleziona l'orario (Durata: {dur_h}h):**")

   await callback.message.edit_text(txt, reply_markup=kb.as_markup(), parse_mode="HTML")
   await state.set_state(Flow.time)

@dp.callback_query(Flow.time, F.data == "custom_time")
async def custom_time_prompt(callback: types.CallbackQuery, state: FSMContext):
   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data=f"dt_{ (await state.get_data())['date'] }"))
   await callback.message.edit_text("✍️ Scrivi l'orario nel formato <b>HH:MM</b> <i>(es. 14:30)</i>:", reply_markup=kb.as_markup(), parse_mode="HTML")
   await state.set_state(Flow.custom_time)

@dp.message(Flow.custom_time)
async def custom_time_input(message: types.Message, state: FSMContext):
   try:
       t_str = message.text.strip()
       datetime.strptime(t_str, "%H:%M") # Validazione formato

       data = await state.get_data()
       sel_date = data.get('date')
       dur_h = data.get('duration')

       # Verifica sovrapposizioni anche sull'orario personalizzato
       intervals = get_booked_intervals()
       year = datetime.now().year
       start_dt = datetime.strptime(f"{sel_date}/{year} {t_str}", "%d/%m/%Y %H:%M")
       if start_dt < datetime.now() - timedelta(days=60):
           start_dt = start_dt.replace(year=year+1)
       end_dt = start_dt + timedelta(hours=dur_h)

       overlap_info = ""
       for b_start, b_end in intervals:
           if start_dt < b_end and end_dt > b_start:
               overlap_info = f"{b_start.strftime('%H:%M')} e le {b_end.strftime('%H:%M')}"
               break

       if overlap_info:
           await message.answer(f"⚠️ L'orario che hai inserito ({t_str}) si sovrappone a una prenotazione già esistente tra le {overlap_info}.\n\n✍️ Riprova scrivendo un orario libero:")
           return

       await state.update_data(time=t_str)
       await render_recap(message, state)
   except:
       await message.answer("⚠️ Formato non valido. Usa HH:MM (es. 14:30).")

@dp.callback_query(Flow.time, F.data.startswith("tm_"))
async def handle_time(callback: types.CallbackQuery, state: FSMContext):
   await state.update_data(time=callback.data.replace("tm_", ""))
   await render_recap(callback, state)

async def render_recap(obj, state):
   data = await state.get_data()
   h = data['duration']
   base_price = calculate_price(data['channels'], h)

   rep_cost = 3.0 if data.get('ext_repost') else 0.0
   fiss_cost = 1.0 if data.get('ext_fiss') else 0.0
   nop_cost = data.get('ext_nopost', 0) * 1.0 * h
   tot = base_price + rep_cost + fiss_cost + nop_cost

   start_t = data['time']
   end_dt = datetime.strptime(start_t, "%H:%M") + timedelta(hours=h)
   end_t = end_dt.strftime("%H:%M")

   await state.update_data(tot=tot, end_t=end_t)

   ch_names = [CHANNELS[c] for c in data['channels']]
   extra_txt = []
   if data.get('ext_repost'): extra_txt.append("Repost")
   if data.get('ext_fiss'): extra_txt.append("Fissato")
   if data.get('ext_nopost', 0) > 0: extra_txt.append(f"No-Post ({data['ext_nopost']}/3)")
   extra_str = ", ".join(extra_txt) if extra_txt else "Nessuna"

   recap = (f"🛒 <b>IL TUO CARRELLO</b>\n\n"
            f"📦 <b>Pacchetto:</b> Sponsor\n"
            f"📺 <b>Canali Scelti:</b> {', '.join(ch_names)}\n"
            f"⏱️ <b>Ore:</b> {h}h\n"
            f"📅 <b>Data:</b> {data['date']}\n"
            f"▶️ <b>Inizio:</b> {start_t} | <b>Fine:</b> {end_t}\n"
            f"➕ <b>Aggiunte:</b> {extra_str}\n\n"
            f"💰 <b>TOTALE DA PAGARE:</b> {tot:.2f}€")

   kb = InlineKeyboardBuilder()
   kb.row(types.InlineKeyboardButton(text="💶 Procedi con il pagamento", callback_data="pay_sponsor"))
   kb.row(types.InlineKeyboardButton(text="🔃 Modifica", callback_data="go_date"), types.InlineKeyboardButton(text="❌ Annulla", callback_data="back_main"))

   if isinstance(obj, types.Message): await obj.answer(recap, reply_markup=kb.as_markup())
   else: await obj.message.edit_text(recap, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "pay_sponsor")
async def pay_sponsor(callback: types.CallbackQuery, state: FSMContext):
   cau = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
   await state.update_data(causale=cau)

   txt = (f"💶 **PROCEDI CON IL PAGAMENTO**\n\n"
          f"IBAN: `{IBAN_DATI}`\n"
          f"Causale: `ADV-{cau}` (⚠️ OBBLIGATORIA)\n\n"
          f"📸 Invia qui sotto lo screenshot del pagamento per completare l'ordine.")

   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="❌ Annulla", callback_data="back_main"))
   await callback.message.edit_text(txt, reply_markup=kb.as_markup())
   await state.set_state(Flow.receipt_sponsor)

@dp.message(Flow.receipt_sponsor, F.photo)
async def rx_sponsor(message: types.Message, state: FSMContext):
   d = await state.get_data(); u = message.from_user
   ch_names = [CHANNELS[c] for c in d['channels']]
   admin_txt = (f"🆕 **NUOVO ORDINE!**\n\n"
                f"👤 Utente: @{u.username} ({u.id})\n"
                f"📦 Acquisto: Sponsor\n"
                f"📺 Canali: {', '.join(ch_names)}\n"
                f"📅 Data: {d['date']}\n"
                f"⏰ {d['time']} -> {d['end_t']}\n"
                f"💰 Totale: {d['tot']:.2f}€\n"
                f"🔑 Causale: ADV-{d['causale']}")

   # Salva in DB come In Attesa
   conn = sqlite3.connect('ads_booking.db')
   conn.execute("INSERT INTO bookings (user_id, type, info, date, start_t, end_t, causale, status) VALUES (?,?,?,?,?,?,?,?)",
                (u.id, "Sponsor", f"{len(d['channels'])} Canali, {d['duration']}h", d['date'], d['time'], d['end_t'], d['causale'], "IN ATTESA"))
   bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
   conn.commit(); conn.close()

   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="✅ APPROVA", callback_data=f"adm_ok_{bid}"), types.InlineKeyboardButton(text="❌ RIFIUTA", callback_data=f"adm_no_{bid}"))
   await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_txt, reply_markup=kb.as_markup())
   await message.answer("✅ Ricevuta inviata! L'ordine è in attesa di approvazione.")
   await state.clear()

# --- FLUSSO INCREMENTI ---
@dp.callback_query(F.data == "buy_increment")
async def buy_increment(callback: types.CallbackQuery, state: FSMContext):
   kb = InlineKeyboardBuilder()
   for k, v in INCREMENT_PACKAGES.items(): kb.add(types.InlineKeyboardButton(text=v, callback_data=f"inc_{k}"))
   kb.adjust(2)
   kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"))
   await callback.message.edit_text("📈 **Scegli il pacchetto Incrementi:**", reply_markup=kb.as_markup())
   await state.set_state(Flow.inc_package)

@dp.callback_query(Flow.inc_package, F.data.startswith("inc_"))
async def inc_package_sel(callback: types.CallbackQuery, state: FSMContext):
   pkg_id = callback.data.replace("inc_", "")
   await state.update_data(inc_pkg=pkg_id, inc_name=INCREMENT_PACKAGES[pkg_id])

   txt = (f"📦 Hai scelto: {INCREMENT_PACKAGES[pkg_id]}\n\n"
          f"⚠️ **Istruzioni Obbligatorie:**\n"
          f"1️⃣ Aggiungi @GlobalStreaming2_bot come admin nel tuo canale/gruppo.\n"
          f"2️⃣ Assicurati di avergli dato il permesso 'Invita Utenti'.\n\n"
          f"🔗 Invia qui sotto il link del canale/gruppo.")
   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="❌ Annulla", callback_data="back_main"))
   await callback.message.edit_text(txt, reply_markup=kb.as_markup())
   await state.set_state(Flow.inc_link)

@dp.message(Flow.inc_link)
async def inc_link_rx(message: types.Message, state: FSMContext):
   await state.update_data(inc_link=message.text)
   txt = ("✅ Link acquisito correttamente.\n\n"
          "Procedi con il pagamento per iniziare la procedura di incremento.")
   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="💸 Procedi al pagamento", callback_data="pay_inc"))
   await message.answer(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "pay_inc")
async def pay_inc(callback: types.CallbackQuery, state: FSMContext):
   cau = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
   await state.update_data(causale=cau)

   txt = (f"💶 **PROCEDI CON IL PAGAMENTO**\n\n"
          f"IBAN: `{IBAN_DATI}`\n"
          f"Causale: `INC-{cau}` (⚠️ OBBLIGATORIA)\n\n"
          f"📸 Invia qui sotto lo screenshot del pagamento.")

   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="❌ Annulla", callback_data="back_main"))
   await callback.message.edit_text(txt, reply_markup=kb.as_markup())
   await state.set_state(Flow.inc_receipt)

@dp.message(Flow.inc_receipt, F.photo)
async def rx_inc(message: types.Message, state: FSMContext):
   d = await state.get_data(); u = message.from_user
   admin_txt = (f"🆕 **NUOVO ORDINE!**\n\n"
                f"👤 Utente: @{u.username} ({u.id})\n"
                f"📦 Acquisto: Incremento ({d['inc_name']})\n"
                f"🔗 Link: {d['inc_link']}\n"
                f"🔑 Causale: INC-{d['causale']}")

   conn = sqlite3.connect('ads_booking.db')
   conn.execute("INSERT INTO bookings (user_id, type, info, date, start_t, end_t, causale, status) VALUES (?,?,?,?,?,?,?,?)",
                (u.id, "Incremento", d['inc_name'], "N/D", "N/D", "N/D", d['causale'], "IN ATTESA"))
   bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
   conn.commit(); conn.close()

   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="✅ APPROVA", callback_data=f"adm_ok_{bid}"), types.InlineKeyboardButton(text="❌ RIFIUTA", callback_data=f"adm_no_{bid}"))
   await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_txt, reply_markup=kb.as_markup())
   await message.answer("✅ Ricevuta inviata! L'ordine è in attesa di approvazione.")
   await state.clear()

# --- ADMIN AZIONI ---
@dp.callback_query(F.data.startswith("adm_ok_"))
async def adm_ok(callback: types.CallbackQuery):
   bid = int(callback.data.replace("adm_ok_", ""))
   conn = sqlite3.connect('ads_booking.db')
   conn.execute("UPDATE bookings SET status = 'APPROVATO' WHERE id = ?", (bid,))
   uid = conn.execute("SELECT user_id FROM bookings WHERE id = ?", (bid,)).fetchone()[0]
   conn.commit(); conn.close()
   await bot.send_message(uid, "🎉 **IL TUO ORDINE È STATO APPROVATO!**")
   await callback.message.edit_caption(caption=callback.message.caption + "\n\n🟢 STATO: APPROVATO")

@dp.callback_query(F.data.startswith("adm_no_"))
async def adm_no(callback: types.CallbackQuery):
   bid = int(callback.data.replace("adm_no_", ""))
   conn = sqlite3.connect('ads_booking.db')
   conn.execute("UPDATE bookings SET status = 'RIFIUTATO' WHERE id = ?", (bid,))
   uid = conn.execute("SELECT user_id FROM bookings WHERE id = ?", (bid,)).fetchone()[0]
   conn.commit(); conn.close()
   await bot.send_message(uid, "❌ **IL TUO ORDINE È STATO RIFIUTATO.** Contatta l'assistenza.")
   await callback.message.edit_caption(caption=callback.message.caption + "\n\n🔴 STATO: RIFIUTATO")

async def main():
   await bot.delete_webhook(drop_pending_updates=True)
   await dp.start_polling(bot)

if __name__ == "__main__":
   Thread(target=run_flask, daemon=True).start()
   try: asyncio.run(main())
   except Exception as e: print("Bot fermato", e)
