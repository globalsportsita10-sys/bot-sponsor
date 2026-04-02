import asyncio
import sqlite3
import random
import string
import logging
import threading # Nuovo: per far girare Flask insieme al Bot
from flask import Flask # Nuovo: per Render
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- CONFIGURAZIONE WEB PER RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running!" # Questo è quello che vedrà UptimeRobot

def run_flask():
    # Render assegna una porta dinamica, Flask la legge automaticamente
    app.run(host='0.0.0.0', port=8080)

# --- CONFIGURAZIONE BOT ---
API_TOKEN = '8660149890:AAFPeMsPAbbFjZID012-NXXyUNGyDaF2gLU'
ADMIN_ID = 8361466889

IBAN_DATI = "IT 00 X 00000 00000 000000000000"
SUMUP_LINK = "https://link.sumup.it/tuolink"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# --- DATABASE INIT ---
def init_db():
    conn = sqlite3.connect('ads_booking.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, joined_date DATETIME)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, start_time DATETIME, end_time DATETIME, user_id INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, price REAL, timestamp DATETIME)''')
    conn.commit()
    conn.close()

init_db()

# --- DATI CANALI E PREZZI ---
CHANNELS_DATA = {
    "goal": {"name": "Goal Highlights ⚽️", "id": "GOAL_ID"},
    "juve": {"name": "Juventus Planet ⚪️⚫️", "id": "JUVE_ID"},
}
for i in range(1, 10):
    CHANNELS_DATA[f"str_{i}"] = {"name": f"Streaming {i} 📺", "id": f"STR{i}_ID"}

INCREMENTS_PRICES = {"1K": 50, "2K": 80, "3K": 120, "5K": 200}

# --- STATI FSM ---
class BotStates(StatesGroup):
    waiting_for_content = State()
    waiting_for_channels = State()
    waiting_for_duration = State()
    waiting_for_extras = State()
    waiting_for_day = State()
    waiting_for_time = State()
    waiting_for_custom_time = State()
    waiting_for_increment_link = State()
    waiting_for_receipt = State()
    waiting_for_broadcast_msg = State()

# --- FUNZIONI UTILS ---
def calculate_total(selected_keys, hours):
    total = 0
    str_count = sum(1 for k in selected_keys if "str_" in k)
    if str_count == 9: total += {3: 25, 6: 35, 12: 50, 24: 65}[hours]
    elif 5 <= str_count <= 8: total += {3: 20, 6: 30, 12: 40, 24: 50}[hours]
    elif 3 <= str_count <= 4: total += {3: 15, 6: 20, 12: 35, 24: 45}[hours]
    else: total += (str_count * {3: 6, 6: 9.5, 12: 15, 24: 19.5}[hours])

    if "goal" in selected_keys: total += {3: 5, 6: 7.5, 12: 11, 24: 13.5}[hours]
    if "juve" in selected_keys: total += {3: 4, 6: 5.5, 12: 8, 24: 12}[hours]
    return total

def generate_causale(user_id):
    rc = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ADV-{user_id}-{rc}"

def has_minimum_space(day_str, channel_ids):
    conn = sqlite3.connect('ads_booking.db')
    cursor = conn.cursor()
    day_start = datetime.strptime(day_str, "%Y-%m-%d")
    day_end = day_start + timedelta(days=1)
    placeholders = ', '.join(['?'] * len(channel_ids))
    if not channel_ids: return True
    cursor.execute(f"SELECT start_time, end_time FROM bookings WHERE channel_id IN ({placeholders}) AND start_time < ? AND end_time > ? ORDER BY start_time ASC", (*channel_ids, day_end, day_start))
    booked = cursor.fetchall()
    conn.close()
    if not booked: return True
    current = day_start
    for s_str, e_str in booked:
        s_dt = datetime.strptime(s_str, "%Y-%m-%d %H:%M:%S")
        e_dt = datetime.strptime(e_str, "%Y-%m-%d %H:%M:%S")
        if (s_dt - current) >= timedelta(hours=3): return True
        if e_dt > current: current = e_dt
    return (day_end - current) >= timedelta(hours=3)

# --- MENU E LOGICA ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    conn = sqlite3.connect('ads_booking.db')
    conn.execute("INSERT OR IGNORE INTO users (user_id, username, joined_date) VALUES (?, ?, ?)", (message.from_user.id, message.from_user.username, datetime.now()))
    conn.commit()
    conn.close()

    if message.from_user.id == ADMIN_ID:
        kb = [[types.InlineKeyboardButton(text="📊 Statistiche", callback_data="admin_stats")],
              [types.InlineKeyboardButton(text="📅 Visualizza Impegni", callback_data="admin_schedule")],
              [types.InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
              [types.InlineKeyboardButton(text="🛒 Vista Utente", callback_data="user_view")]]
        await message.answer("🛠 **PANNELLO AMMINISTRATORE**", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await show_main_menu(message)

async def show_main_menu(obj):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📢 Acquista Sponsor", callback_data="buy_sponsor"))
    builder.row(types.InlineKeyboardButton(text="🚀 Acquista Incrementi", callback_data="buy_increment"))
    builder.row(
        types.InlineKeyboardButton(text="🔍 Stato Ordine", callback_data="check_status"),
        types.InlineKeyboardButton(text="📋 Listino Prezzi", url="https://t.me/GlobalSportsSponsor")
    )
    builder.row(types.InlineKeyboardButton(text="🆘 Assistenza", url="https://t.me/GlobalSportsContatto"))
    builder.row(types.InlineKeyboardButton(text="⚙️ Come Funziona", callback_data="how_it_works"))

    txt = "👋 **Benvenuto nel Global Advertising Bot!**\n\nIl sistema più veloce e automatizzato per gestire le tue promozioni.\nUsa i bottoni qui sotto per iniziare."
    if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=builder.as_markup())
    else: await obj.message.edit_text(txt, reply_markup=builder.as_markup())

# --- AGGIUNTA LOGICHE MANCANTI (COME FUNZIONA & STATO) ---
@dp.callback_query(F.data == "how_it_works")
async def how_it_works_logic(callback: types.CallbackQuery):
    guida = (
        "⚙️ **COME FUNZIONA IL BOT**\n\n"
        "📢 **SPONSOR:** Invia il post, scegli canali/orari e paga con causale univoca.\n"
        "📈 **INCREMENTI:** Scegli il pacchetto, aggiungi @GlobalStreaming2_bot come admin con permessi 'invito' e paga.\n\n"
        "💡 *Riceverai una causale per ogni ordine: usala sempre nel pagamento!*"
    )
    kb = [[types.InlineKeyboardButton(text="⬅️ Torna al Menu", callback_data="user_view")]]
    await callback.message.edit_text(guida, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "check_status")
async def status_logic(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()
    if current_state == BotStates.waiting_for_receipt:
        txt = f"🔍 **STATO ORDINE: IN SOSPESO**\n\nImporto: **{data.get('total')}€**\nCausale: `{data.get('causale')}`"
        kb = [[types.InlineKeyboardButton(text="💳 Continua", callback_data="r_cont")], [types.InlineKeyboardButton(text="❌ Annulla", callback_data="r_canc")]]
    else:
        txt = "🔍 **STATO ORDINE**\n\nNessun ordine in sospeso."
        kb = [[types.InlineKeyboardButton(text="⬅️ Torna al Menu", callback_data="user_view")]]
    await callback.message.edit_text(txt, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "user_view")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(callback)

# --- FLUSSO INCREMENTI ---
@dp.callback_query(F.data == "buy_increment")
async def start_inc(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for k, v in INCREMENTS_PRICES.items(): kb.row(types.InlineKeyboardButton(text=f"🚀 Pacchetto {k} - {v}€", callback_data=f"inc_{k}"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Torna al Menu", callback_data="user_view"))
    await callback.message.edit_text("🚀 **INCREMENTI**\nScegli il pacchetto:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("inc_"))
async def inc_instructions(callback: types.CallbackQuery, state: FSMContext):
    pkg = callback.data.split("_")[1]
    await state.update_data(inc_pkg=pkg, total=INCREMENTS_PRICES[pkg])
    await callback.message.edit_text(f"✅ Pacchetto {pkg}\n\n1️⃣ Aggiungi @GlobalStreaming2_bot come Admin.\n2️⃣ Permesso 'Invitare utenti'.\n\n🔗 Invia il link del canale:")
    await state.set_state(BotStates.waiting_for_increment_link)

@dp.message(BotStates.waiting_for_increment_link)
async def inc_link(message: types.Message, state: FSMContext):
    await state.update_data(inc_link=message.text)
    d = await state.get_data()
    cau = generate_causale(message.from_user.id)
    await state.update_data(causale=cau)
    await message.answer(f"💳 **PAGAMENTO**\nTotale: {d['total']}€\nCausale: `{cau}`\n\nIBAN: `{IBAN_DATI}`\n\n📸 Invia ricevuta:")
    await state.set_state(BotStates.waiting_for_receipt)

# --- FLUSSO SPONSOR (VERSIONE LIGHT PER SPAZIO) ---
@dp.callback_query(F.data == "buy_sponsor")
async def sponsor_init(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Invia il post da sponsorizzare:")
    await state.set_state(BotStates.waiting_for_content)

@dp.message(BotStates.waiting_for_content)
async def get_content(message: types.Message, state: FSMContext):
    await state.update_data(msg_id=message.message_id, sel_chans=[])
    await show_chan_sel(message, [])
    await state.set_state(BotStates.waiting_for_channels)

async def show_chan_sel(msg, sel):
    builder = InlineKeyboardBuilder()
    for k, v in CHANNELS_DATA.items(): builder.row(types.InlineKeyboardButton(text=f"{'✅' if k in sel else '◻️'} {v['name']}", callback_data=f"sel_{k}"))
    if sel: builder.row(types.InlineKeyboardButton(text="➡️ Prosegui", callback_data="chans_ok"))
    if isinstance(msg, types.Message): await msg.answer("📺 Canali:", reply_markup=builder.as_markup())
    else: await msg.message.edit_reply_markup(reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("sel_"), BotStates.waiting_for_channels)
async def toggle_ch(callback: types.CallbackQuery, state: FSMContext):
    k = callback.data.split("_")[1]; d = await state.get_data(); sel = d['sel_chans']
    if k in sel: sel.remove(k)
    else: sel.append(k)
    await state.update_data(sel_chans=sel); await show_chan_sel(callback, sel)

@dp.callback_query(F.data == "chans_ok", BotStates.waiting_for_channels)
async def dur_sel(callback: types.CallbackQuery):
    kb = [[types.InlineKeyboardButton(text="3h", callback_data="h_3"), types.InlineKeyboardButton(text="6h", callback_data="h_6")]]
    await callback.message.edit_text("⏳ Durata:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(BotStates.waiting_for_duration)

@dp.callback_query(F.data.startswith("h_"), BotStates.waiting_for_duration)
async def time_sel_start(callback: types.CallbackQuery, state: FSMContext):
    h = int(callback.data.split("_")[1]); cau = generate_causale(callback.from_user.id)
    d = await state.get_data(); tot = calculate_total(d['sel_chans'], h)
    await state.update_data(total=tot, causale=cau)
    await callback.message.edit_text(f"💳 **PAGAMENTO**\nTotale: {tot}€\nCausale: `{cau}`\n\nIBAN: `{IBAN_DATI}`\n\n📸 Invia ricevuta:")
    await state.set_state(BotStates.waiting_for_receipt)

# --- GESTIONE RICEVUTA & ADMIN ---
@dp.message(BotStates.waiting_for_receipt, F.photo)
async def receipt_received(msg: types.Message, state: FSMContext):
    d = await state.get_data(); u = msg.from_user
    info = f"📦 {d.get('inc_pkg', 'Sponsor')}"
    adm_txt = f"📩 **ORDINE**\n👤 @{u.username}\n{info}\n💰 {d['total']}€\n🔑 Causale: `{d['causale']}`"
    kb = [[types.InlineKeyboardButton(text="✅ APPROVA", callback_data=f"ap_{u.id}"), types.InlineKeyboardButton(text="❌ RIFIUTA", callback_data=f"re_{u.id}")]]
    await bot.send_photo(ADMIN_ID, msg.photo[-1].file_id, caption=adm_txt, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await msg.answer("✅ Inviata! Attendi conferma."); await state.clear()

@dp.callback_query(F.data.startswith("ap_"))
async def adm_ap(cb: types.CallbackQuery):
    u_id = int(cb.data.split("_")[1])
    await cb.message.edit_caption(caption=cb.message.caption + "\n\n🟢 **APPROVATO**")
    await bot.send_message(u_id, "🎉 Pagamento confermato!")

# --- AVVIO COMBINATO ---
async def main():
    # Avvia Flask in un thread separato
    threading.Thread(target=run_flask, daemon=True).start()

    # Avvia il Bot
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
