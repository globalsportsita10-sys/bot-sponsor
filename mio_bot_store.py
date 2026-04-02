import asyncio
import sqlite3
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

# --- CONFIGURAZIONE WEB PER RENDER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURAZIONE BOT ---
API_TOKEN = '8513979649:AAHceiZHqQDqU5gRVhILGD2WMC9OfevT7kw'
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
    c.execute('CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, info TEXT, date TEXT, time TEXT)')
    conn.commit(); conn.close()

init_db()

# --- DATI CANALI ---
CHANNELS_DATA = {
    "goal": "Goal Highlights ⚽️",
    "juve": "Juventus Planet ⚪️⚫️",
    "str_1": "Streaming 1 📺", "str_2": "Streaming 2 📺",
    "str_3": "Streaming 3 📺", "str_4": "Streaming 4 📺",
    "str_5": "Streaming 5 📺", "str_6": "Streaming 6 📺",
    "str_7": "Streaming 7 📺", "str_8": "Streaming 8 📺",
    "str_9": "Streaming 9 📺"
}

INCREMENTS_PRICES = {"1K": 50, "2K": 80, "3K": 120, "5K": 200}

class Flow(StatesGroup):
    channels = State()
    duration = State()
    extras = State()
    date = State()
    start_time = State()
    receipt = State()
    inc_setup = State()
    broadcast = State()

# --- MENU ---
async def main_menu(obj):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📢 Acquista Sponsor", callback_data="buy_sponsor"))
    builder.row(types.InlineKeyboardButton(text="🚀 Acquista Incrementi", callback_data="buy_increment"))
    builder.row(types.InlineKeyboardButton(text="🔍 Stato Ordine", callback_data="order_status"),
                types.InlineKeyboardButton(text="📋 Listino Prezzi", url="https://t.me/GlobalSportsSponsor"))
    builder.row(types.InlineKeyboardButton(text="🆘 Assistenza", url="https://t.me/GlobalSportsContatto"))
    builder.row(types.InlineKeyboardButton(text="⚙️ Come Funziona", callback_data="how_works"))
    txt = "👋 **Benvenuto nel Global Advertising Bot!**\nScegli un'opzione qui sotto:"
    if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=builder.as_markup())
    else: await obj.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    conn = sqlite3.connect('ads_booking.db')
    conn.execute("INSERT OR IGNORE INTO users VALUES (?,?)", (message.from_user.id, message.from_user.username))
    conn.commit(); conn.close()
    if message.from_user.id == ADMIN_ID: await admin_panel(message)
    else: await main_menu(message)

async def admin_panel(obj):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="📅 Prenotazioni", callback_data="admin_list"))
    kb.row(types.InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_bc"))
    txt = "🛠 **PANNELLO ADMIN**"
    if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=kb.as_markup())
    else: await obj.message.edit_text(txt, reply_markup=kb.as_markup())

# ==========================================
# LOGICA PREZZI SPONSOR (AGGIORNATA)
# ==========================================
def calculate_sponsor_price(channels, hours):
    total = 0.0
    h_str = str(hours)

    # Prezzi Goal Highlights
    goal_prices = {"3": 5, "6": 7.5, "12": 11, "24": 13.5}
    # Prezzi Juventus Planet
    juve_prices = {"3": 4, "6": 5.5, "12": 8, "24": 12}
    # Prezzi Singolo Streaming
    str_single = {"3": 6, "6": 9.5, "12": 15, "24": 19.5}

    if "goal" in channels: total += goal_prices.get(h_str, 0)
    if "juve" in channels: total += juve_prices.get(h_str, 0)

    # Logica Canali Streaming
    streaming_selected = [c for c in channels if c.startswith("str_")]
    num_str = len(streaming_selected)

    if num_str == 9: # Tutti i canali
        all_str = {"3": 25, "6": 35, "12": 50, "24": 65}
        total += all_str.get(h_str, 0)
    elif 5 <= num_str <= 8:
        mid_str = {"3": 20, "6": 30, "12": 40, "24": 50}
        total += mid_str.get(h_str, 0)
    elif 3 <= num_str <= 4:
        low_str = {"3": 15, "6": 20, "12": 35, "24": 45}
        total += low_str.get(h_str, 0)
    elif 1 <= num_str <= 2:
        total += (num_str * str_single.get(h_str, 0))

    return total

# ==========================================
# FLUSSO SPONSOR
# ==========================================
@dp.callback_query(F.data == "buy_sponsor")
async def step_ch(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(channels=[], extras=[])
    await render_ch(callback, [])

async def render_ch(callback, sel):
    kb = InlineKeyboardBuilder()
    for k, v in CHANNELS_DATA.items():
        kb.add(types.InlineKeyboardButton(text=f"{v} {'✅' if k in sel else ''}", callback_data=f"ch_{k}"))
    kb.adjust(2)
    kb.row(types.InlineKeyboardButton(text="🌟 Seleziona Tutto", callback_data="ch_all"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_dur"))
    await callback.message.edit_text("📢 **SPONSOR: SELEZIONA I CANALI**", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("ch_"))
async def handle_ch(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data(); sel = data.get('channels', [])
    code = callback.data.replace("ch_", "")
    if code == "all": sel = list(CHANNELS_DATA.keys())
    elif code in sel: sel.remove(code)
    else: sel.append(code)
    await state.update_data(channels=sel); await render_ch(callback, sel)

@dp.callback_query(F.data == "go_dur")
async def step_dur(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for h in [3, 6, 12, 24]: kb.add(types.InlineKeyboardButton(text=f"{h} Ore", callback_data=f"dur_{h}"))
    kb.adjust(2); kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="buy_sponsor"))
    await callback.message.edit_text("⏳ **Scegli la durata del post:**", reply_markup=kb.as_markup())
    await state.set_state(Flow.duration)

@dp.callback_query(Flow.duration, F.data.startswith("dur_"))
async def handle_dur(callback: types.CallbackQuery, state: FSMContext):
    h = int(callback.data.replace("dur_", ""))
    await state.update_data(duration=h)
    await step_ex(callback, state)

async def step_ex(obj, state):
    data = await state.get_data(); ex = data.get('extras', [])
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text=f"📌 Fissato (+1€) {'✅' if 'fissato' in ex else '❌'}", callback_data="ex_fissato"))
    kb.row(types.InlineKeyboardButton(text=f"🔄 Repost (+3€) {'✅' if 'repost' in ex else '❌'}", callback_data="ex_repost"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="go_dur"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_date"))
    txt = "✨ **Aggiunte Extra:**"
    if isinstance(obj, types.CallbackQuery): await obj.message.edit_text(txt, reply_markup=kb.as_markup())
    else: await obj.answer(txt, reply_markup=kb.as_markup()); await obj.message.edit_text(txt, reply_markup=kb.as_markup())
    await state.set_state(Flow.extras)

@dp.callback_query(Flow.extras, F.data.startswith("ex_"))
async def handle_ex(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data(); ex = data.get('extras', [])
    val = callback.data.replace("ex_", "")
    if val in ex: ex.remove(val)
    else: ex.append(val)
    await state.update_data(extras=ex); await step_ex(callback, state)

@dp.callback_query(Flow.extras, F.data == "go_date")
async def step_date(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for i in range(5):
        d = (datetime.now() + timedelta(days=i)).strftime("%d/%m")
        kb.add(types.InlineKeyboardButton(text=d, callback_data=f"dt_{d}"))
    kb.adjust(2); kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="go_dur"))
    await callback.message.edit_text("📅 **Seleziona la data:**", reply_markup=kb.as_markup())
    await state.set_state(Flow.date)

@dp.callback_query(Flow.date, F.data.startswith("dt_"))
async def step_time(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(date=callback.data.replace("dt_", ""))
    kb = InlineKeyboardBuilder()
    for t in ["09:00", "12:00", "15:00", "18:00"]: kb.add(types.InlineKeyboardButton(text=t, callback_data=f"tm_{t}"))
    kb.adjust(2); kb.row(types.InlineKeyboardButton(text="✍️ Personalizzata", callback_data="tm_custom"))
    await callback.message.edit_text("⏰ **Orario di inizio:**", reply_markup=kb.as_markup())
    await state.set_state(Flow.start_time)

@dp.callback_query(Flow.start_time, F.data.startswith("tm_"))
async def handle_tm(callback: types.CallbackQuery, state: FSMContext):
    t = callback.data.replace("tm_", "")
    if t == "custom": await callback.message.edit_text("⏰ **Scrivi l'orario (es. 14:30):**")
    else:
        await state.update_data(start_time=t)
        await send_final_recap(callback.message, state)

async def send_final_recap(message, state):
    data = await state.get_data()

    # Calcolo Prezzo Base dinamico
    base_price = calculate_sponsor_price(data['channels'], data['duration'])
    # Calcolo Extra
    extra_price = (1 if "fissato" in data.get('extras', []) else 0) + (3 if "repost" in data.get('extras', []) else 0)

    total = base_price + extra_price
    await state.update_data(total_cost=total)

    recap = (f"🛒 **RIEPILOGO ORDINE**\n\n"
             f"📺 Canali: {len(data['channels'])}\n"
             f"⏳ Durata: {data['duration']}h\n"
             f"⏰ Inizio: {data['start_time']}\n"
             f"📅 Data: {data['date']}\n"
             f"✨ Extra: {', '.join(data.get('extras', []))}\n\n"
             f"💰 **TOTALE: {total}€**")

    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="💳 Paga Ora", callback_data="pay_now"))
    await message.answer(recap, reply_markup=kb.as_markup())
    await state.set_state(Flow.receipt)

# --- GESTORI MANUALI ---
@dp.message(Flow.start_time)
async def manual_tm(message: types.Message, state: FSMContext):
    await state.update_data(start_time=message.text)
    await send_final_recap(message, state)

# ==========================================
# INCREMENTI E ADMIN (PREZZI FISSI)
# ==========================================
@dp.callback_query(F.data == "buy_increment")
async def step_inc(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for k, v in INCREMENTS_PRICES.items(): kb.add(types.InlineKeyboardButton(text=f"🚀 {k} - {v}€", callback_data=f"inc_{k}"))
    kb.adjust(2); kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"))
    await callback.message.edit_text("🚀 **SCEGLI PACCHETTO INCREMENTI:**", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("inc_"))
async def inc_instr(callback: types.CallbackQuery, state: FSMContext):
    pkg = callback.data.replace("inc_", "")
    await state.update_data(pkg=pkg, total_cost=INCREMENTS_PRICES[pkg], channels=["Incrementi"])
    await callback.message.edit_text(f"✅ Pacchetto {pkg}\nInvia qui il **LINK DEL CANALE**:")
    await state.set_state(Flow.inc_setup)

@dp.message(Flow.inc_setup)
async def handle_inc_link(message: types.Message, state: FSMContext):
    await state.update_data(channel_link=message.text)
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="💳 Paga Ora", callback_data="pay_now"))
    await message.answer(f"✅ Link ricevuto: {message.text}", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "pay_now")
async def pay_info(callback: types.CallbackQuery, state: FSMContext):
    cau = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    await state.update_data(causale_code=cau)
    await callback.message.edit_text(f"💳 **PAGAMENTO**\n\nIBAN: `{IBAN_DATI}`\nCausale: `ADV-{cau}`\n\n📸 **Invia lo screenshot della ricevuta!**")
    await state.set_state(Flow.receipt)

@dp.message(Flow.receipt, F.photo)
async def handle_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data(); u = message.from_user
    recap_admin = f"📩 **ORDINE**\n👤 @{u.username}\n💰 {data.get('total_cost')}€\n🔑 `ADV-{data.get('causale_code')}`"
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="✅ OK", callback_data=f"adm_ok_{u.id}"), types.InlineKeyboardButton(text="❌ NO", callback_data=f"adm_no_{u.id}"))
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=recap_admin, reply_markup=kb.as_markup())
    await message.answer("✅ Ricevuta inviata! Attendi conferma."); await state.clear()

@dp.callback_query(F.data.startswith("adm_ok_"))
async def admin_approve(callback: types.CallbackQuery):
    uid = int(callback.data.replace("adm_ok_", ""))
    await bot.send_message(uid, "🎉 **IL TUO ORDINE È STATO APPROVATO!**")
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n🟢 **APPROVATO**")

@dp.callback_query(F.data == "admin_list")
async def admin_list(callback: types.CallbackQuery):
    conn = sqlite3.connect('ads_booking.db'); c = conn.cursor()
    c.execute("SELECT * FROM bookings ORDER BY id DESC LIMIT 5"); rows = c.fetchall(); conn.close()
    txt = "📅 **PRENOTAZIONI:**\n\n" + "\n".join([f"ID {r[0]}: {r[1][:30]}..." for r in rows]) if rows else "Nessuna."
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="admin_menu_back"))
    await callback.message.edit_text(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "admin_menu_back")
async def admin_back(callback: types.CallbackQuery): await admin_panel(callback)

@dp.callback_query(F.data == "admin_bc")
async def admin_bc(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📢 **Scrivi il messaggio broadcast:**"); await state.set_state(Flow.broadcast)

@dp.message(Flow.broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('ads_booking.db'); c = conn.cursor()
    c.execute("SELECT user_id FROM users"); users = c.fetchall(); conn.close()
    for u in users:
        try: await bot.send_message(u[0], message.text)
        except: pass
    await message.answer("📢 Inviato!"); await state.clear()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    try: asyncio.run(main())
    except: pass
