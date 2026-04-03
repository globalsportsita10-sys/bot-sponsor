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
            times.append((datetime.strptime(s, "%H:%M").time(), datetime.strptime(e, "%H:%M").time()))
        except: continue
    return sorted(times)

def is_slot_available(date_str, duration_h):
    bookings = get_day_bookings(date_str)
    curr = datetime.combine(datetime.today(), time(0,0))
    end_d = datetime.combine(datetime.today(), time(23,59))
    for b_s, b_e in bookings:
        bs_dt = datetime.combine(datetime.today(), b_s)
        if (bs_dt - curr).total_seconds() / 3600 >= duration_h: return True
        curr = datetime.combine(datetime.today(), b_e)
    return (end_d - curr).total_seconds() / 3600 >= duration_h

init_db()

CHANNELS_DATA = {
    "goal": "Goal Highlights ⚽️", "juve": "Juventus Planet ⚪️⚫️",
    "str_1": "Streaming 1 📺", "str_2": "Streaming 2 📺", "str_3": "Streaming 3 📺",
    "str_4": "Streaming 4 📺", "str_5": "Streaming 5 📺", "str_6": "Streaming 6 📺",
    "str_7": "Streaming 7 📺", "str_8": "Streaming 8 📺", "str_9": "Streaming 9 📺"
}
INCREMENTS_PRICES = {"1K": 50, "2K": 80, "3K": 120, "5K": 200}

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

# --- MENU PRINCIPALE ---
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
    kb.row(types.InlineKeyboardButton(text="⚙️ Come Funziona", callback_data="how_works"))
    txt = "👋 **Benvenuto nel Global Advertising Bot!**"
    if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=kb.as_markup())
    else: await obj.message.edit_text(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "how_works")
async def how_it_works(callback: types.CallbackQuery):
    txt = "⚙️ **COME FUNZIONA**\n\n1. Scegli Sponsor o Incrementi.\n2. Seleziona canali e orario.\n3. Paga e invia lo screenshot.\n4. Attendi l'approvazione!"
    await callback.message.edit_text(txt, reply_markup=InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main")).as_markup())

@dp.callback_query(F.data == "order_status")
async def check_status(callback: types.CallbackQuery):
    conn = sqlite3.connect('ads_booking.db'); c = conn.cursor()
    c.execute("SELECT info, date, start_t FROM bookings WHERE user_id = ? ORDER BY id DESC LIMIT 5", (callback.from_user.id,))
    rows = c.fetchall(); conn.close()
    txt = "🔍 **I TUOI ORDINI:**\n\n" + ("\n".join([f"📦 {r[0]}\n📅 {r[1]} ore {r[2]}\n✅ Approvato" for r in rows]) if rows else "Nessun ordine trovato.")
    await callback.message.edit_text(txt, reply_markup=InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main")).as_markup())

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear(); await main_menu(callback)

# --- SPONSOR FLOW ---
@dp.callback_query(F.data == "buy_sponsor")
async def step_ch(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(type_order="Sponsor", channels=[], extras=[])
    await render_ch(callback, [])

async def render_ch(callback, sel):
    kb = InlineKeyboardBuilder()
    for k, v in CHANNELS_DATA.items(): kb.add(types.InlineKeyboardButton(text=f"{v} {'✅' if k in sel else ''}", callback_data=f"ch_{k}"))
    kb.adjust(2)
    if len(sel) == len(CHANNELS_DATA): kb.row(types.InlineKeyboardButton(text="❌ Deseleziona Tutto", callback_data="ch_none"))
    else: kb.row(types.InlineKeyboardButton(text="🌟 Seleziona Tutto", callback_data="ch_all"))
    kb.row(types.InlineKeyboardButton(text="⬅️", callback_data="back_main"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_dur"))
    await callback.message.edit_text("📢 **CANALI:**", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("ch_"))
async def handle_ch(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data(); sel = data.get('channels', [])
    c = callback.data.replace("ch_", "")
    if c == "all": sel = list(CHANNELS_DATA.keys())
    elif c == "none": sel = []
    elif c in sel: sel.remove(c)
    else: sel.append(c)
    await state.update_data(channels=sel); await render_ch(callback, sel)

@dp.callback_query(F.data == "go_dur")
async def step_dur(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for h in [3, 6, 12, 24]: kb.add(types.InlineKeyboardButton(text=f"{h} Ore", callback_data=f"dur_{h}"))
    kb.adjust(2).row(types.InlineKeyboardButton(text="⬅️", callback_data="buy_sponsor"))
    await callback.message.edit_text("⏳ **Durata:**", reply_markup=kb.as_markup()); await state.set_state(Flow.duration)

@dp.callback_query(Flow.duration, F.data.startswith("dur_"))
async def handle_dur(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(duration=int(callback.data.replace("dur_", ""))); await step_ex(callback, state)

async def step_ex(obj, state):
    data = await state.get_data(); ex = data.get('extras', [])
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text=f"📌 Fissato (+1€) {'✅' if 'fissato' in ex else '❌'}", callback_data="ex_fissato")).row(types.InlineKeyboardButton(text=f"🔄 Repost (+3€) {'✅' if 'repost' in ex else '❌'}", callback_data="ex_repost")).row(types.InlineKeyboardButton(text="⬅️", callback_data="go_dur"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_date"))
    await obj.message.edit_text("✨ **Extra:**", reply_markup=kb.as_markup()); await state.set_state(Flow.extras)

@dp.callback_query(Flow.extras, F.data.startswith("ex_"))
async def handle_ex(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data(); ex = data.get('extras', [])
    v = callback.data.replace("ex_", "")
    if v in ex: ex.remove(v)
    else: ex.append(v)
    await state.update_data(extras=ex); await step_ex(callback, state)

@dp.callback_query(F.data == "go_date")
@dp.callback_query(Flow.extras, F.data == "go_date")
@dp.callback_query(Flow.receipt, F.data == "go_date")
async def step_date(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for i in range(30):
        d_str = (datetime.now() + timedelta(days=i)).strftime("%d/%m")
        if not is_slot_available(d_str, 3): kb.add(types.InlineKeyboardButton(text=f"{d_str} 🚫", callback_data="day_full"))
        else: kb.add(types.InlineKeyboardButton(text=d_str, callback_data=f"dt_{d_str}"))
    kb.adjust(3).row(types.InlineKeyboardButton(text="⬅️", callback_data="go_dur"))
    await callback.message.edit_text("📅 **Data:**", reply_markup=kb.as_markup()); await state.set_state(Flow.date)

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
    await callback.message.edit_text(f"⏰ **Orari ({d_sel}):**", reply_markup=kb.as_markup()); await state.set_state(Flow.start_time)

@dp.callback_query(Flow.start_time, F.data.startswith("tm_"))
async def handle_tm(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(start_time=callback.data.replace("tm_", "")); await send_final_recap(callback.message, state)

async def send_final_recap(message, state):
    data = await state.get_data()
    total = calculate_sponsor_price(data['channels'], data['duration']) + (1 if "fissato" in data.get('extras', []) else 0) + (3 if "repost" in data.get('extras', []) else 0)
    h_start = datetime.strptime(data['start_time'], "%H:%M")
    h_end = (h_start + timedelta(hours=data['duration'])).strftime("%H:%M")
    await state.update_data(total_cost=total, end_time=h_end)
    recap = f"🛒 **RIEPILOGO**\n\n📺 Canali: {len(data['channels'])}\n⏳ Durata: {data['duration']}h\n⏰ {data['start_time']} -> {h_end}\n📅 {data['date']}\n💰 **TOTALE: {total}€**"
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="💳 Paga", callback_data="pay_now")).row(types.InlineKeyboardButton(text="✏️ Modifica", callback_data="go_date"), types.InlineKeyboardButton(text="❌", callback_data="back_main"))
    await message.edit_text(recap, reply_markup=kb.as_markup()); await state.set_state(Flow.receipt)

# --- INCREMENTI ---
@dp.callback_query(F.data == "buy_increment")
async def step_inc(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(type_order="Incrementi")
    kb = InlineKeyboardBuilder()
    for k, v in INCREMENTS_PRICES.items(): kb.add(types.InlineKeyboardButton(text=f"🚀 {k} - {v}€", callback_data=f"inc_{k}"))
    kb.adjust(2).row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"))
    await callback.message.edit_text("🚀 **PACCHETTI:**", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("inc_"))
async def inc_instr(callback: types.CallbackQuery, state: FSMContext):
    p = callback.data.replace("inc_", ""); await state.update_data(pkg=p, total_cost=INCREMENTS_PRICES[p])
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="buy_increment"))
    await callback.message.edit_text(f"✅ {p}\nInvia il **LINK**:", reply_markup=kb.as_markup()); await state.set_state(Flow.inc_setup)

@dp.message(Flow.inc_setup)
async def handle_inc_link(message: types.Message, state: FSMContext):
    await state.update_data(channel_link=message.text)
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="💳 Paga", callback_data="pay_now")).row(types.InlineKeyboardButton(text="❌ Annulla", callback_data="back_main"))
    await message.answer("✅ Link ricevuto", reply_markup=kb.as_markup())

# --- PAGAMENTO ---
@dp.callback_query(F.data == "pay_now")
async def pay_info(callback: types.CallbackQuery, state: FSMContext):
    cau = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    await state.update_data(causale_code=cau)
    await callback.message.edit_text(f"💳 **PAGAMENTO**\nIBAN: `{IBAN_DATI}`\nCausale: `ADV-{cau}`\n\n📸 **Invia screenshot!**", reply_markup=InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="❌ Annulla", callback_data="back_main")).as_markup())
    await state.set_state(Flow.receipt)

@dp.message(Flow.receipt, F.photo)
async def handle_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data(); u = message.from_user
    recap = f"📩 **ORDINE**\n👤 @{u.username} ({u.id})\n📦 **{data.get('type_order')}**\n"
    if data.get('type_order') == "Sponsor": recap += f"⏳ {data.get('duration')}h | {data.get('start_time')}-{data.get('end_time')}\n📅 {data.get('date')}\n"
    else: recap += f"🚀 {data.get('pkg')} | {data.get('channel_link')}\n"
    recap += f"💰 **{data.get('total_cost')}€** | 🔑 `ADV-{data.get('causale_code')}`"
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="✅ OK", callback_data=f"adm_ok_{u.id}"), types.InlineKeyboardButton(text="❌ NO", callback_data=f"adm_no_{u.id}"))
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=recap, reply_markup=kb.as_markup())
    await message.answer("✅ Inviata!"); await state.clear()

# --- ADMIN ---
async def admin_panel(obj):
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="📅 Prenotazioni", callback_data="admin_list"), types.InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_bc")).row(types.InlineKeyboardButton(text="🏠 Menu", callback_data="back_main"))
    if isinstance(obj, types.Message): await obj.answer("🛠 ADMIN", reply_markup=kb.as_markup())
    else: await obj.message.edit_text("🛠 ADMIN", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "admin_list")
async def admin_list(callback: types.CallbackQuery):
    conn = sqlite3.connect('ads_booking.db'); c = conn.cursor()
    c.execute("SELECT * FROM bookings ORDER BY id DESC LIMIT 10"); rows = c.fetchall(); conn.close()
    txt = "📅 **PRENOTAZIONI:**\n" + ("\n".join([f"#{r[0]} | {r[2]} | {r[3]} ({r[4]}-{r[5]})" for r in rows]) if rows else "Vuoto.")
    await callback.message.edit_text(txt, reply_markup=InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️", callback_data="admin_menu_back")).as_markup())

@dp.callback_query(F.data.startswith("adm_ok_"))
async def admin_approve(callback: types.CallbackQuery):
    uid = int(callback.data.replace("adm_ok_", "")); lines = callback.message.caption.split('\n')
    info = lines[2]; d_val = "N/D"; s_t = "00:00"; dur_h = 0
    for l in lines:
        if "📅" in l: d_val = l.replace("📅 ", "").strip()
        if "⏳" in l:
            try:
                dur_h = int(l.split('h')[0].replace('⏳','').strip())
                s_t = l.split('|')[1].strip().split('-')[0].strip()
            except: pass
    conn = sqlite3.connect('ads_booking.db')
    start_dt = datetime.strptime(f"{d_val} {s_t}", "%d/%m %H:%M")
    end_dt = start_dt + timedelta(hours=dur_h)
    first_day_end = end_dt.strftime("%H:%M") if end_dt.date() == start_dt.date() else "23:59"
    conn.execute("INSERT INTO bookings (user_id, info, date, start_t, end_t) VALUES (?,?,?,?,?)", (uid, info, d_val, s_t, first_day_end))
    if end_dt.date() > start_dt.date():
        next_day_str = end_dt.strftime("%d/%m")
        conn.execute("INSERT INTO bookings (user_id, info, date, start_t, end_t) VALUES (?,?,?,?,?)", (uid, info + " (Cont.)", next_day_str, "00:00", end_dt.strftime("%H:%M")))
    conn.commit(); conn.close()
    await bot.send_message(uid, "🎉 **IL TUO ORDINE È STATO APPROVATO E CALENDARIZZATO!**")
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n🟢 APPROVATO")

@dp.callback_query(F.data == "admin_bc")
async def admin_bc_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📢 Messaggio:"); await state.set_state(Flow.broadcast)

@dp.message(Flow.broadcast)
async def admin_bc_send(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('ads_booking.db'); users = conn.execute("SELECT user_id FROM users").fetchall(); conn.close()
    for u in users:
        try: await bot.send_message(u[0], message.text); await asyncio.sleep(0.05)
        except: continue
    await message.answer("✅ Inviato"); await state.clear(); await admin_panel(message)

@dp.callback_query(F.data == "admin_menu_back")
async def admin_back(callback: types.CallbackQuery): await admin_panel(callback)

@dp.callback_query(F.data == "day_full")
async def day_full_info(callback: types.CallbackQuery):
    await callback.answer("Giorno senza slot liberi di 3h! 🚫", show_alert=True)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    try: asyncio.run(main())
    except: pass
