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
API_TOKEN = '8513979649:AAE4-Zwc7hRhmO21Q9lm-bREOEePefJjmCI'
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

# --- MENU PRINCIPALE ---
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

@dp.callback_query(F.data == "how_works")
async def how_it_works(callback: types.CallbackQuery):
    txt = ("⚙️ **COME FUNZIONA**\n\n1. Scegli tra Sponsor o Incrementi.\n2. Seleziona i canali e l'orario.\n3. Paga tramite IBAN e invia lo screenshot.\n4. Attendi l'approvazione!")
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"))
    await callback.message.edit_text(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "order_status")
async def check_status(callback: types.CallbackQuery):
    txt = ("🔍 **STATO ORDINE**\n\nNon ci sono ordini attivi al momento.\nSe hai inviato una ricevuta, l'admin la sta controllando.")
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"))
    await callback.message.edit_text(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear(); await main_menu(callback)

# ==========================================
# LOGICA PREZZI SPONSOR
# ==========================================
def calculate_sponsor_price(channels, hours):
    total = 0.0
    h_str = str(hours)
    goal_p = {"3": 5, "6": 7.5, "12": 11, "24": 13.5}
    juve_p = {"3": 4, "6": 5.5, "12": 8, "24": 12}
    str_s = {"3": 6, "6": 9.5, "12": 15, "24": 19.5}
    if "goal" in channels: total += goal_p.get(h_str, 0)
    if "juve" in channels: total += juve_p.get(h_str, 0)
    st_sel = [c for c in channels if c.startswith("str_")]
    n = len(st_sel)
    if n == 9: total += {"3": 25, "6": 35, "12": 50, "24": 65}.get(h_str, 0)
    elif 5 <= n <= 8: total += {"3": 20, "6": 30, "12": 40, "24": 50}.get(h_str, 0)
    elif 3 <= n <= 4: total += {"3": 15, "6": 20, "12": 35, "24": 45}.get(h_str, 0)
    elif 1 <= n <= 2: total += (n * str_s.get(h_str, 0))
    return total

# ==========================================
# FLUSSO SPONSOR
# ==========================================
@dp.callback_query(F.data == "buy_sponsor")
async def step_ch(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(type_order="Sponsor") # Identificatore ordine
    await render_ch(callback, [])

async def render_ch(callback, sel):
    kb = InlineKeyboardBuilder()
    for k, v in CHANNELS_DATA.items():
        kb.add(types.InlineKeyboardButton(text=f"{v} {'✅' if k in sel else ''}", callback_data=f"ch_{k}"))
    kb.adjust(2)
    kb.row(types.InlineKeyboardButton(text="🌟 Seleziona Tutto", callback_data="ch_all"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_dur"))
    await callback.message.edit_text("📢 **SELEZIONA I CANALI:**", reply_markup=kb.as_markup())

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
    await callback.message.edit_text("⏳ **Scegli la durata:**", reply_markup=kb.as_markup())
    await state.set_state(Flow.duration)

@dp.callback_query(Flow.duration, F.data.startswith("dur_"))
async def handle_dur(callback: types.CallbackQuery, state: FSMContext):
    h = int(callback.data.replace("dur_", ""))
    await state.update_data(duration=h); await step_ex(callback, state)

async def step_ex(obj, state):
    data = await state.get_data(); ex = data.get('extras', [])
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text=f"📌 Fissato (+1€) {'✅' if 'fissato' in ex else '❌'}", callback_data="ex_fissato"))
    kb.row(types.InlineKeyboardButton(text=f"🔄 Repost (+3€) {'✅' if 'repost' in ex else '❌'}", callback_data="ex_repost"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="go_dur"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_date"))
    await obj.message.edit_text("✨ **Aggiunte Extra:**", reply_markup=kb.as_markup())
    await state.set_state(Flow.extras)

@dp.callback_query(Flow.extras, F.data.startswith("ex_"))
async def handle_ex(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data(); ex = data.get('extras', [])
    val = callback.data.replace("ex_", "")
    if val in ex: ex.remove(val)
    else: ex.append(val)
    await state.update_data(extras=ex); await step_ex(callback, state)

@dp.callback_query(F.data == "go_date") # Tasto Modifica punta qui
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
    kb.adjust(2)
    kb.row(types.InlineKeyboardButton(text="✍️ Personalizzata", callback_data="tm_custom"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="go_date"))
    await callback.message.edit_text("⏰ **Orario di inizio:**", reply_markup=kb.as_markup())
    await state.set_state(Flow.start_time)

@dp.callback_query(Flow.start_time, F.data.startswith("tm_"))
async def handle_tm(callback: types.CallbackQuery, state: FSMContext):
    t = callback.data.replace("tm_", "")
    if t == "custom": await callback.message.edit_text("⏰ **Scrivi l'orario (es. 14:30):**")
    else: await state.update_data(start_time=t); await send_final_recap(callback.message, state)

async def send_final_recap(message, state):
    data = await state.get_data()
    base = calculate_sponsor_price(data['channels'], data['duration'])
    extra = (1 if "fissato" in data.get('extras', []) else 0) + (3 if "repost" in data.get('extras', []) else 0)
    total = base + extra

    # Calcolo ora di fine
    try:
        h_start = datetime.strptime(data['start_time'], "%H:%M")
        h_end = (h_start + timedelta(hours=int(data['duration']))).strftime("%H:%M")
    except: h_end = "N/D"

    await state.update_data(total_cost=total, end_time=h_end)

    recap = (f"🛒 **RIEPILOGO ORDINE**\n\n📺 Canali: {len(data['channels'])}\n⏳ Durata: {data['duration']}h\n"
             f"⏰ Inizio: {data['start_time']} -> Fine: {h_end}\n📅 Data: {data['date']}\n✨ Extra: {', '.join(data.get('extras', []))}\n\n💰 **TOTALE: {total}€**")
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="💳 Paga Ora", callback_data="pay_now"))
    kb.row(types.InlineKeyboardButton(text="✏️ Modifica", callback_data="go_date"),
           types.InlineKeyboardButton(text="❌ Annulla", callback_data="back_main"))
    await message.edit_text(recap, reply_markup=kb.as_markup())
    await state.set_state(Flow.receipt)

@dp.message(Flow.start_time)
async def manual_tm(message: types.Message, state: FSMContext):
    await state.update_data(start_time=message.text); await send_final_recap(message, state)

# ==========================================
# INCREMENTI E PAGAMENTI
# ==========================================
@dp.callback_query(F.data == "buy_increment")
async def step_inc(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(type_order="Incrementi")
    kb = InlineKeyboardBuilder()
    for k, v in INCREMENTS_PRICES.items(): kb.add(types.InlineKeyboardButton(text=f"🚀 {k} - {v}€", callback_data=f"inc_{k}"))
    kb.adjust(2); kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"))
    await callback.message.edit_text("🚀 **SCEGLI PACCHETTO INCREMENTI:**", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("inc_"))
async def inc_instr(callback: types.CallbackQuery, state: FSMContext):
    pkg = callback.data.replace("inc_", "")
    await state.update_data(pkg=pkg, total_cost=INCREMENTS_PRICES[pkg])
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="buy_increment"))
    await callback.message.edit_text(f"✅ Pacchetto {pkg}\nInvia qui il **LINK DEL CANALE**:", reply_markup=kb.as_markup())
    await state.set_state(Flow.inc_setup)

@dp.message(Flow.inc_setup)
async def handle_inc_link(message: types.Message, state: FSMContext):
    await state.update_data(channel_link=message.text)
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="💳 Paga Ora", callback_data="pay_now"))
    kb.row(types.InlineKeyboardButton(text="❌ Annulla", callback_data="back_main"))
    await message.answer(f"✅ Link ricevuto: {message.text}", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "pay_now")
async def pay_info(callback: types.CallbackQuery, state: FSMContext):
    cau = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    await state.update_data(causale_code=cau)
    txt = (f"💳 **PAGAMENTO**\n\nIBAN: `{IBAN_DATI}`\nCausale: `ADV-{cau}`\n\n📸 **Invia lo screenshot della ricevuta!**")
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="❌ Annulla", callback_data="back_main"))
    await callback.message.edit_text(txt, reply_markup=kb.as_markup())
    await state.set_state(Flow.receipt)

@dp.message(Flow.receipt, F.photo)
async def handle_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data(); u = message.from_user

    # Costruzione Recap per Admin
    recap_admin = (f"📩 **NUOVO ORDINE RICEVUTO**\n"
                   f"👤 Cliente: @{u.username if u.username else 'N/D'} (ID: `{u.id}`)\n"
                   f"📦 Tipo: **{data.get('type_order')}**\n")

    if data.get('type_order') == "Sponsor":
        recap_admin += (f"⏳ Durata Totale: {data.get('duration')} ore\n"
                        f"⏰ Inizio: {data.get('start_time')} | Fine: {data.get('end_time')}\n"
                        f"📅 Data: {data.get('date')}\n"
                        f"📺 Canali: {len(data.get('channels', []))}\n")
    else:
        recap_admin += f"🚀 Pacchetto: {data.get('pkg')}\n🔗 Link: {data.get('channel_link')}\n"

    recap_admin += (f"\n💰 **TOTALE: {data.get('total_cost')}€**\n"
                    f"🔑 Causale: `ADV-{data.get('causale_code')}`")

    kb = InlineKeyboardBuilder().row(
        types.InlineKeyboardButton(text="✅ OK", callback_data=f"adm_ok_{u.id}"),
        types.InlineKeyboardButton(text="❌ NO", callback_data=f"adm_no_{u.id}")
    )

    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=recap_admin, reply_markup=kb.as_markup())
    await message.answer("✅ Ricevuta inviata! Attendi conferma."); await state.clear()

async def admin_panel(obj):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="📅 Prenotazioni", callback_data="admin_list"))
    kb.row(types.InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_bc"))
    if isinstance(obj, types.Message): await obj.answer("🛠 **PANNELLO ADMIN**", reply_markup=kb.as_markup())
    else: await obj.message.edit_text("🛠 **PANNELLO ADMIN**", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("adm_ok_"))
async def admin_approve(callback: types.CallbackQuery):
    uid = int(callback.data.replace("adm_ok_", ""))
    await bot.send_message(uid, "🎉 **ORDINE APPROVATO!**"); await callback.message.edit_caption(caption=callback.message.caption + "\n🟢 OK")

@dp.callback_query(F.data == "admin_menu_back")
async def admin_back(callback: types.CallbackQuery): await admin_panel(callback)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    try: asyncio.run(main())
    except: pass
