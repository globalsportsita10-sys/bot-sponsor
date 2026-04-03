import asyncio
import sqlite3
import random
import string
import logging
import os
from threading import Thread
from flask import Flask
from datetime import datetime, timedelta, time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage

# --- CONFIG ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running!"
def run_flask():
   port = int(os.environ.get("PORT", 10000))
   app.run(host='0.0.0.0', port=port)

API_TOKEN = '8513979649:AAEIzdfkyR2c8-oejkhn-wahI2g4xKhw9zM'
ADMIN_ID = 8361466889
IBAN_DATI = "IT 00 X 00000 00000 000000000000"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- DATABASE ---
def init_db():
   conn = sqlite3.connect('ads_booking.db')
   c = conn.cursor()
   c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT)')
   c.execute('CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, info TEXT, date TEXT, start_t TEXT, end_t TEXT)')
   conn.commit(); conn.close()

def get_day_bookings(date_str):
   conn = sqlite3.connect('ads_booking.db')
   c = conn.cursor()
   c.execute("SELECT start_t, end_t FROM bookings WHERE date = ?", (date_str,))
   res = c.fetchall(); conn.close()
   times = []
   for s, e in res:
       try:
           t_start = datetime.strptime(s, "%H:%M").time()
           t_end = datetime.strptime(e, "%H:%M").time()
           times.append((t_start, t_end))
       except: continue
   return sorted(times)

# LOGICA DI BLOCCO AUTOMATICO 🚫
def is_slot_available(date_str, duration_h=3):
   bookings = get_day_bookings(date_str)
   if not bookings: return True

   # Convertiamo le prenotazioni in minuti (0-1440)
   segments = []
   for b_start, b_end in bookings:
       m_start = b_start.hour * 60 + b_start.minute
       m_end = b_end.hour * 60 + b_end.minute
       if m_end <= m_start: m_end = 1440
       segments.append((m_start, m_end))

   # Uniamo segmenti sovrapposti o consecutivi per semplificare il calcolo dei buchi
   segments.sort()
   if not segments: return True

   merged = [segments[0]]
   for current in segments[1:]:
       prev_start, prev_end = merged[-1]
       if current[0] <= prev_end:
           merged[-1] = (prev_start, max(prev_end, current[1]))
       else:
           merged.append(current)

   # Controlliamo se esiste un buco di almeno 3 ore (180 min)
   required_gap = 180
   last_end = 0
   for start, end in merged:
       if (start - last_end) >= required_gap:
           return True
       last_end = max(last_end, end)

   if (1440 - last_end) >= required_gap:
       return True

   return False

init_db()

# --- DATI ---
CHANNELS_DATA = {
   "goal": "Goal Highlights ⚽️", "juve": "Juventus Planet ⚪️⚫️",
   "str_1": "Streaming 1 📺", "str_2": "Streaming 2 📺", "str_3": "Streaming 3 📺",
   "str_4": "Streaming 4 📺", "str_5": "Streaming 5 📺", "str_6": "Streaming 6 📺",
   "str_7": "Streaming 7 📺", "str_8": "Streaming 8 📺", "str_9": "Streaming 9 📺"
}

class Flow(StatesGroup):
   channels = State(); duration = State(); extras = State(); date = State()
   start_time = State(); receipt = State(); inc_setup = State(); broadcast = State()

def calculate_sponsor_price(channels, hours):
   total = 0.0; h = str(hours)
   if "goal" in channels: total += {"3": 5, "6": 7.5, "12": 11, "24": 13.5}.get(h, 0)
   if "juve" in channels: total += {"3": 4, "6": 5.5, "12": 8, "24": 12}.get(h, 0)
   st = [c for c in channels if c.startswith("str_")]
   n = len(st)
   if n == 9: total += {"3": 25, "6": 35, "12": 50, "24": 65}.get(h, 0)
   elif 5 <= n <= 8: total += {"3": 20, "6": 30, "12": 40, "24": 50}.get(h, 0)
   elif 3 <= n <= 4: total += {"3": 15, "6": 20, "12": 35, "24": 45}.get(h, 0)
   elif 1 <= n <= 2: total += n * {"3": 6, "6": 9.5, "12": 15, "24": 19.5}.get(h, 0)
   return float(total)

# --- HANDLERS ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
   await state.clear()
   conn = sqlite3.connect('ads_booking.db')
   conn.execute("INSERT OR IGNORE INTO users VALUES (?,?)", (message.from_user.id, message.from_user.username))
   conn.commit(); conn.close()
   if message.from_user.id == ADMIN_ID: await admin_panel(message)
   else: await main_menu(message)

async def main_menu(obj):
   kb = InlineKeyboardBuilder()
   kb.row(types.InlineKeyboardButton(text="📢 Acquista Sponsor", callback_data="buy_sponsor"))
   kb.row(types.InlineKeyboardButton(text="🚀 Acquista Incrementi", callback_data="buy_increment"))
   kb.row(types.InlineKeyboardButton(text="🔍 Stato Ordine", callback_data="order_status"),
          types.InlineKeyboardButton(text="📋 Listino", url="https://t.me/GlobalSportsSponsor"))
   kb.row(types.InlineKeyboardButton(text="🆘 Assistenza", url="https://t.me/GlobalSportsContatto"))
   txt = "👋 **Benvenuto nel Global Advertising Bot!**"
   if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=kb.as_markup())
   else: await obj.message.edit_text(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
   await state.clear(); await main_menu(callback)

@dp.callback_query(F.data == "buy_sponsor")
async def step_ch(callback: types.CallbackQuery, state: FSMContext):
   await state.update_data(channels=[], extras=[])
   await render_ch(callback, [])

async def render_ch(callback, sel):
   kb = InlineKeyboardBuilder()
   for k, v in CHANNELS_DATA.items(): kb.add(types.InlineKeyboardButton(text=f"{v} {'✅' if k in sel else ''}", callback_data=f"ch_{k}"))
   kb.adjust(2)
   kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_dur"))
   await callback.message.edit_text("📢 **CANALI:**", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("ch_"))
async def handle_ch(callback: types.CallbackQuery, state: FSMContext):
   data = await state.get_data(); sel = data.get('channels', [])
   c = callback.data.replace("ch_", "")
   if c in sel: sel.remove(c)
   else: sel.append(c)
   await state.update_data(channels=sel); await render_ch(callback, sel)

@dp.callback_query(F.data == "go_dur")
async def step_dur(callback: types.CallbackQuery, state: FSMContext):
   kb = InlineKeyboardBuilder()
   for h in [3, 6, 12, 24]: kb.add(types.InlineKeyboardButton(text=f"{h} Ore", callback_data=f"dur_{h}"))
   kb.adjust(2).row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="buy_sponsor"))
   await callback.message.edit_text("⏳ **DURATA:**", reply_markup=kb.as_markup()); await state.set_state(Flow.duration)

@dp.callback_query(Flow.duration, F.data.startswith("dur_"))
async def handle_dur(callback: types.CallbackQuery, state: FSMContext):
   await state.update_data(duration=int(callback.data.replace("dur_", "")))
   await step_ex(callback, state)

async def step_ex(obj, state):
   data = await state.get_data(); ex = data.get('extras', [])
   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text=f"📌 Fissato (+1€) {'✅' if 'fissato' in ex else '❌'}", callback_data="ex_fissato")).row(types.InlineKeyboardButton(text=f"🔄 Repost (+3€) {'✅' if 'repost' in ex else '❌'}", callback_data="ex_repost")).row(types.InlineKeyboardButton(text="⬅️", callback_data="go_dur"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_date"))
   await obj.message.edit_text("✨ **EXTRA:**", reply_markup=kb.as_markup()); await state.set_state(Flow.extras)

@dp.callback_query(Flow.extras, F.data.startswith("ex_"))
async def handle_ex(callback: types.CallbackQuery, state: FSMContext):
   data = await state.get_data(); ex = data.get('extras', [])
   v = callback.data.replace("ex_", "")
   if v in ex: ex.remove(v)
   else: ex.append(v)
   await state.update_data(extras=ex); await step_ex(callback, state)

@dp.callback_query(F.data == "go_date")
@dp.callback_query(Flow.extras, F.data == "go_date")
async def step_date(callback: types.CallbackQuery, state: FSMContext):
   kb = InlineKeyboardBuilder()
   for i in range(14):
       d_str = (datetime.now() + timedelta(days=i)).strftime("%d/%m")
       if not is_slot_available(d_str):
           kb.add(types.InlineKeyboardButton(text=f"{d_str} 🚫", callback_data="day_full"))
       else:
           kb.add(types.InlineKeyboardButton(text=d_str, callback_data=f"dt_{d_str}"))
   kb.adjust(3).row(types.InlineKeyboardButton(text="⬅️", callback_data="go_dur"))
   await callback.message.edit_text("📅 **DATA:**", reply_markup=kb.as_markup()); await state.set_state(Flow.date)

@dp.callback_query(Flow.date, F.data.startswith("dt_"))
async def step_time(callback: types.CallbackQuery, state: FSMContext):
   d_sel = callback.data.replace("dt_", ""); await state.update_data(date=d_sel)
   data = await state.get_data(); dur = data.get('duration', 3); bookings = get_day_bookings(d_sel)
   kb = InlineKeyboardBuilder()
   for pt in ["09:00", "12:00", "15:00", "18:00", "21:00"]:
       pt_dt = datetime.strptime(pt, "%H:%M"); pt_end = pt_dt + timedelta(hours=dur); conflict = False
       for sb, eb in bookings:
           s_dt = datetime.combine(datetime.today(), sb); e_dt = datetime.combine(datetime.today(), eb)
           if not (pt_end <= s_dt or pt_dt >= e_dt): conflict = True; break
       if not conflict: kb.add(types.InlineKeyboardButton(text=pt, callback_data=f"tm_{pt}"))
   kb.adjust(2).row(types.InlineKeyboardButton(text="⬅️", callback_data="go_date"))
   await callback.message.edit_text(f"⏰ **ORARI ({d_sel}):**", reply_markup=kb.as_markup()); await state.set_state(Flow.start_time)

@dp.callback_query(Flow.start_time, F.data.startswith("tm_"))
async def handle_tm(callback: types.CallbackQuery, state: FSMContext):
   t_start = callback.data.replace("tm_", ""); await state.update_data(start_time=t_start)
   data = await state.get_data()
   total = calculate_sponsor_price(data['channels'], data['duration']) + (1 if "fissato" in data.get('extras', []) else 0) + (3 if "repost" in data.get('extras', []) else 0)
   h_end = (datetime.strptime(t_start, "%H:%M") + timedelta(hours=data['duration'])).strftime("%H:%M")
   await state.update_data(total_cost=total, end_time=h_end)
   recap = f"🛒 **RIEPILOGO**\n\n📺 Canali: {len(data['channels'])}\n⏳ Durata: {data['duration']}h\n⏰ {t_start} -> {h_end}\n📅 {data['date']}\n💰 **TOTALE: {total}€**"
   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="💳 Paga", callback_data="pay_now")).row(types.InlineKeyboardButton(text="❌", callback_data="back_main"))
   await callback.message.edit_text(recap, reply_markup=kb.as_markup()); await state.set_state(Flow.receipt)

@dp.callback_query(F.data == "pay_now")
async def pay_now(callback: types.CallbackQuery):
   await callback.message.edit_text(f"💳 **PAGAMENTO**\n\nIBAN: `{IBAN_DATI}`\n\n📸 Invia lo screenshot della ricevuta qui sotto:")

@dp.message(Flow.receipt, F.photo)
async def handle_receipt(message: types.Message, state: FSMContext):
   data = await state.get_data(); u = message.from_user
   caption = f"📩 **NUOVO ORDINE**\n👤 @{u.username} ({u.id})\n⏳ {data['duration']}h | {data['start_time']}-{data['end_time']}\n📅 {data['date']}\n💰 {data['total_cost']}€"
   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="✅ APPROVA", callback_data=f"adm_ok_{u.id}"), types.InlineKeyboardButton(text="❌ RIFIUTA", callback_data=f"adm_no_{u.id}"))
   await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=kb.as_markup())
   await message.answer("✅ Ricevuta inviata! Attendi conferma."); await state.clear()

@dp.callback_query(F.data.startswith("adm_ok_"))
async def admin_approve(callback: types.CallbackQuery):
   uid = int(callback.data.replace("adm_ok_", "")); lines = callback.message.caption.split('\n')
   try:
       dur_h = int(lines[2].split('h')[0].replace('⏳','').strip())
       times = lines[2].split('|')[1].strip().split('-')
       s_t = times[0].strip(); e_t = times[1].strip()
       d_val = lines[3].replace('📅','').strip()

       conn = sqlite3.connect('ads_booking.db')
       conn.execute("INSERT INTO bookings (user_id, info, date, start_t, end_t) VALUES (?,?,?,?,?)", (uid, "Slot", d_val, s_t, e_t))
       if dur_h >= 24: # Se 24h, blocca anche il giorno dopo
           next_d = (datetime.strptime(d_val, "%d/%m") + timedelta(days=1)).strftime("%d/%m")
           conn.execute("INSERT INTO bookings (user_id, info, date, start_t, end_t) VALUES (?,?,?,?,?)", (uid, "Slot 24h", next_d, "00:00", "23:59"))
       conn.commit(); conn.close()
       await bot.send_message(uid, "🎉 **ORDINE APPROVATO!**"); await callback.message.edit_caption(caption=callback.message.caption + "\n\n🟢 APPROVATO")
   except: await callback.answer("Errore processamento")

@dp.callback_query(F.data == "day_full")
async def day_full(callback: types.CallbackQuery):
   await callback.answer("Giorno pieno! 🚫", show_alert=True)

async def admin_panel(message):
   kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_bc")).row(types.InlineKeyboardButton(text="🏠 Menu", callback_data="back_main"))
   await message.answer("🛠 **PANNELLO ADMIN**", reply_markup=kb.as_markup())

async def main():
   await bot.delete_webhook(drop_pending_updates=True)
   await dp.start_polling(bot)

if __name__ == "__main__":
   Thread(target=run_flask, daemon=True).start()
   asyncio.run(main())
