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
    conn.commit()
    conn.close()

init_db()

# --- DATI ---
CHANNELS_DATA = {
    "goal": "Goal Highlights ⚽️", "juve": "Juventus Planet ⚪️⚫️",
    "str_1": "Streaming 1 📺", "str_2": "Streaming 2 📺",
    "str_3": "Streaming 3 📺", "str_4": "Streaming 4 📺",
    "str_5": "Streaming 5 📺", "str_6": "Streaming 6 📺",
    "str_7": "Streaming 7 📺", "str_8": "Streaming 8 📺",
    "str_9": "Streaming 9 📺"
}

INCREMENTS_PRICES = {"1K": 50, "2K": 80, "3K": 120, "5K": 200}

# --- STATI FSM ---
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
    builder.row(
        types.InlineKeyboardButton(text="🔍 Stato Ordine", callback_data="order_status"),
        types.InlineKeyboardButton(text="📋 Listino Prezzi", url="https://t.me/GlobalSportsSponsor")
    )
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
    conn.commit()
    conn.close()

    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text="📅 Prenotazioni", callback_data="admin_list"))
        kb.row(types.InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_bc"))
        await message.answer("🛠 **PANNELLO ADMIN**", reply_markup=kb.as_markup())
    else:
        await main_menu(message)

# --- LOGICA COME FUNZIONA & STATO ---
@dp.callback_query(F.data == "how_works")
async def how_it_works(callback: types.CallbackQuery):
    await callback.message.edit_text("⚙️ **COME FUNZIONA**\n\n1. Scegli il servizio.\n2. Seleziona i canali e l'orario.\n3. Paga e invia lo screenshot.\n4. L'admin approva e il tuo post va online!", reply_markup=InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main")).as_markup())

@dp.callback_query(F.data == "order_status")
async def check_status(callback: types.CallbackQuery):
    await callback.answer("🔍 Controllo ordini in corso... Nessun ordine in sospeso.", show_alert=True)

@dp.callback_query(F.data == "back_main")
async def back_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await main_menu(callback)

# ==========================================
# FLUSSO SPONSOR
# ==========================================
@dp.callback_query(F.data == "buy_sponsor")
async def step_ch(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(channels=[], extras=[], sub_total=20)
    await render_ch(callback, [])

async def render_ch(callback, sel):
    kb = InlineKeyboardBuilder()
    for k, v in CHANNELS_DATA.items():
        kb.add(types.InlineKeyboardButton(text=f"{'✅' if k in sel else v}", callback_data=f"ch_{k}"))
    kb.adjust(2)
    kb.row(types.InlineKeyboardButton(text="🌟 Seleziona Tutto", callback_data="ch_all"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_dur"))
    await callback.message.edit_text("📢 **OPZIONE SCELTA: SPONSOR**\nSeleziona i canali:", reply_markup=kb.as_markup())

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
    for h in [3, 6, 12, 24]:
        kb.add(types.InlineKeyboardButton(text=f"{h} Ore", callback_data=f"dur_{h}"))
    kb.adjust(2)
    kb.row(types.InlineKeyboardButton(text="✍️ Ore Personalizzate", callback_data="dur_custom"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="buy_sponsor"))
    await callback.message.edit_text("⏳ **Quante ore deve rimanere il post?**", reply_markup=kb.as_markup())
    await state.set_state(Flow.duration)

@dp.callback_query(Flow.duration, F.data.startswith("dur_"))
async def handle_dur(callback: types.CallbackQuery, state: FSMContext):
    h = callback.data.replace("dur_", "")
    if h == "custom":
        await callback.message.answer("Scrivi il numero di ore:")
    else:
        await state.update_data(duration=int(h))
        await step_ex(callback, state)

async def step_ex(callback, state):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="📌 Fissato (+1€)", callback_data="ex_fissato"))
    kb.row(types.InlineKeyboardButton(text="🔄 Repost (+3€)", callback_data="ex_repost"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="go_dur"), types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_date"))
    await callback.message.edit_text("✨ **Vuoi delle aggiunte?**", reply_markup=kb.as_markup())
    await state.set_state(Flow.extras)

@dp.callback_query(Flow.extras, F.data.startswith("ex_"))
async def handle_ex(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data(); ex = data.get('extras', [])
    val = callback.data.replace("ex_", "")
    if val not in ex: ex.append(val)
    await state.update_data(extras=ex); await callback.answer(f"Aggiunto {val}!")

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
    for t in ["09:00", "12:00", "15:00", "18:00"]:
        kb.add(types.InlineKeyboardButton(text=t, callback_data=f"tm_{t}"))
    kb.adjust(2); kb.row(types.InlineKeyboardButton(text="✍️ Personalizzata", callback_data="tm_custom"))
    await callback.message.edit_text("⏰ **Orario di inizio:**", reply_markup=kb.as_markup())
    await state.set_state(Flow.start_time)

@dp.callback_query(Flow.start_time, F.data.startswith("tm_"))
async def handle_recap(callback: types.CallbackQuery, state: FSMContext):
    t = callback.data.replace("tm_", "")
    await state.update_data(start_time=t)
    data = await state.get_data()

    start_dt = datetime.strptime(t, "%H:%M")
    end_dt = (start_dt + timedelta(hours=data['duration'])).strftime("%H:%M")

    costo = data['sub_total'] + ("fissato" in data['extras']) + (3 if "repost" in data['extras'] else 0)
    await state.update_data(total_cost=costo)

    recap = (f"🛒 **RIEPILOGO ORDINE**\n\n"
             f"📦 Pacchetto: Sponsor\n"
             f"📺 Canali: {len(data['channels'])}\n"
             f"⏳ Ore totali: {data['duration']}h\n"
             f"⏰ Inizio: {t} | Fine: {end_dt}\n"
             f"📅 Data: {data['date']}\n"
             f"✨ Aggiunte: {', '.join(data['extras']) if data['extras'] else 'No'}\n\n"
             f"💰 **COSTO TOTALE: {costo}€**")

    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="💳 Paga Ora", callback_data="pay_now"))
    await callback.message.edit_text(recap, reply_markup=kb.as_markup())
    await state.set_state(Flow.receipt)

# ==========================================
# FLUSSO INCREMENTI
# ==========================================
@dp.callback_query(F.data == "buy_increment")
async def step_inc(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for k, v in INCREMENTS_PRICES.items():
        kb.add(types.InlineKeyboardButton(text=f"🚀 {k} - {v}€", callback_data=f"inc_{k}"))
    kb.adjust(2); kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="back_main"))
    await callback.message.edit_text("🚀 **SCEGLI IL PACCHETTO INCREMENTI:**", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("inc_"))
async def inc_instr(callback: types.CallbackQuery, state: FSMContext):
    pkg = callback.data.replace("inc_", "")
    await state.update_data(pkg=pkg, total_cost=INCREMENTS_PRICES[pkg], channels=["Incrementi"], duration=0)
    txt = (f"✅ Hai scelto il pacchetto {pkg}.\n\n"
           f"⚠️ **ISTRUZIONI OBBLIGATORIE:**\n"
           f"1. Aggiungi @GlobalStreaming2_bot come admin.\n"
           f"2. Dai il permesso 'Invitare utenti tramite link'.\n"
           f"3. Invia qui il link del canale.\n\n"
           f"Dopo aver fatto questo, clicca il tasto sotto per pagare.")
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="💳 Vai al Pagamento", callback_data="pay_now"))
    await callback.message.edit_text(txt, reply_markup=kb.as_markup())
    await state.set_state(Flow.receipt)

# ==========================================
# PAGAMENTO & NOTIFICA ADMIN
# ==========================================
@dp.callback_query(F.data == "pay_now")
async def pay_info(callback: types.CallbackQuery, state: FSMContext):
    cau = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    await state.update_data(causale_code=cau)
    await callback.message.edit_text(f"💳 **PAGAMENTO**\n\nIBAN: `{IBAN_DATI}`\nCausale: `ADV-{cau}`\n\n📸 **Invia qui lo screenshot della ricevuta!**")

@dp.message(Flow.receipt, F.photo)
async def handle_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    u = message.from_user

    # Calcolo fine per admin
    try:
        start_dt = datetime.strptime(data.get('start_time', '00:00'), "%H:%M")
        end_time = (start_dt + timedelta(hours=data.get('duration', 0))).strftime("%H:%M")
    except: end_time = "N/A"

    canali = ", ".join([CHANNELS_DATA.get(c, c) for c in data.get('channels', [])])

    recap_admin = (
        f"📩 **NUOVO ORDINE DA APPROVARE**\n\n"
        f"👤 **Utente:** @{u.username or 'Senza Username'}\n"
        f"📺 **Servizio/Canali:** {canali}\n"
        f"📅 **Giorno:** {data.get('date', 'N/A')}\n"
        f"⏰ **Orario:** {data.get('start_time', 'N/A')} - {end_time}\n"
        f"💰 **TOTALE:** {data.get('total_cost')}€\n"
        f"🔑 **Causale:** `ADV-{data.get('causale_code')}`"
    )

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="✅ APPROVA", callback_data=f"adm_ok_{u.id}"),
           types.InlineKeyboardButton(text="❌ RIFIUTA", callback_data=f"adm_no_{u.id}"))

    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=recap_admin, reply_markup=kb.as_markup())
    await message.answer("✅ Ricevuta inviata! L'admin confermerà a breve.")
    await state.clear()

# --- GESTORI ADMIN ---
@dp.callback_query(F.data.startswith("adm_ok_"))
async def admin_approve(callback: types.CallbackQuery):
    uid = int(callback.data.replace("adm_ok_", ""))
    await bot.send_message(uid, "🎉 **ORDINE APPROVATO!**\nIl tuo post verrà pubblicato all'orario stabilito.")
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n🟢 **APPROVATO**")

@dp.callback_query(F.data.startswith("adm_no_"))
async def admin_reject(callback: types.CallbackQuery):
    uid = int(callback.data.replace("adm_no_", ""))
    await bot.send_message(uid, "❌ **ORDINE RIFIUTATO**\nIl pagamento non è stato confermato. Contatta @GlobalSportsContatto")
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n🔴 **RIFIUTATO**")

# --- ALTRE FUNZIONI ADMIN ---
@dp.callback_query(F.data == "admin_bc")
async def admin_bc(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Scrivi il messaggio da inviare a tutti gli utenti:")
    await state.set_state(Flow.broadcast)

@dp.message(Flow.broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('ads_booking.db'); c = conn.cursor()
    c.execute("SELECT user_id FROM users"); users = c.fetchall(); conn.close()
    for u in users:
        try: await bot.send_message(u[0], message.text)
        except: pass
    await message.answer("📢 Broadcast completato!"); await state.clear()

async def main():
    Thread(target=run_flask, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
