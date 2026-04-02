import asyncio
import sqlite3
import random
import string
import logging
import os
import threading
from flask import Flask
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- CONFIGURAZIONE WEB PER RENDER (FIX PORTA) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    # Render assegna una porta dinamica tramite variabile d'ambiente
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURAZIONE BOT ---
API_TOKEN = '8660149890:AAFPeMsPAbbFjZID012-NXXyUNGyDaF2gLU'
ADMIN_ID = 8361466889

IBAN_DATI = "IT 00 X 00000 00000 000000000000" # Metti il tuo IBAN reale
SUMUP_LINK = "https://link.sumup.it/tuolink"  # Metti il tuo link SumUp

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect('ads_booking.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, joined_date DATETIME)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, start_time DATETIME, end_time DATETIME, user_id INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, price REAL, timestamp DATETIME)''')
    conn.commit()
    conn.close()

init_db()

# --- DATI ---
CHANNELS_DATA = {"goal": {"name": "Goal Highlights ⚽️"}, "juve": {"name": "Juventus Planet ⚪️⚫️"}}
for i in range(1, 10): CHANNELS_DATA[f"str_{i}"] = {"name": f"Streaming {i} 📺"}

INCREMENTS_PRICES = {"1K": 50, "2K": 80, "3K": 120, "5K": 200}

class BotStates(StatesGroup):
    waiting_for_content = State()
    waiting_for_channels = State()
    waiting_for_duration = State()
    waiting_for_extras = State()
    waiting_for_day = State()
    waiting_for_time = State()
    waiting_for_increment_link = State()
    waiting_for_receipt = State()
    waiting_for_broadcast_msg = State()

# --- UTILS ---
def generate_causale(user_id):
    rc = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ADV-{user_id}-{rc}"

# --- MENU PRINCIPALE ---
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

    txt = "👋 **Benvenuto nel Global Advertising Bot!**\n\nUsa i bottoni qui sotto per iniziare."
    if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=builder.as_markup())
    else: await obj.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id == ADMIN_ID:
        kb = [[types.InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
              [types.InlineKeyboardButton(text="🛒 Vista Utente", callback_data="user_view")]]
        await message.answer("🛠 **ADMIN PANEL**", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await show_main_menu(message)

# --- LOGICA INFO ---
@dp.callback_query(F.data == "how_it_works")
async def how_it_works(callback: types.CallbackQuery):
    txt = (
        "⚙️ **COME FUNZIONA IL BOT**\n\n"
        "📢 **SPONSOR:** Scegli i canali, la data e paga con la causale fornita.\n\n"
        "📈 **INCREMENTI:**\n"
        "1. Scegli il pacchetto.\n"
        "2. Aggiungi @GlobalStreaming2_bot come Admin nel tuo canale.\n"
        "3. Dai il permesso 'Invitare utenti'.\n"
        "4. Invia il link e la ricevuta."
    )
    await callback.message.edit_text(txt, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Menu", callback_data="user_view")]]))

@dp.callback_query(F.data == "check_status")
async def check_status(callback: types.CallbackQuery, state: FSMContext):
    curr = await state.get_state()
    if curr == BotStates.waiting_for_receipt:
        data = await state.get_data()
        txt = f"🔍 **ORDINE IN SOSPESO**\n\nTotale: **{data.get('total')}€**\nCausale: `{data.get('causale')}`"
        kb = [[types.InlineKeyboardButton(text="💳 Paga", callback_data="r_cont")], [types.InlineKeyboardButton(text="❌ Annulla", callback_data="r_canc")]]
    else:
        txt = "🔍 **STATO ORDINE**\n\nNessun ordine attivo."
        kb = [[types.InlineKeyboardButton(text="⬅️ Menu", callback_data="user_view")]]
    await callback.message.edit_text(txt, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

# --- FLUSSO INCREMENTI ---
@dp.callback_query(F.data == "buy_increment")
async def inc_start(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    for k, v in INCREMENTS_PRICES.items(): kb.row(types.InlineKeyboardButton(text=f"🚀 {k} - {v}€", callback_data=f"inc_{k}"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Menu", callback_data="user_view"))
    await callback.message.edit_text("🚀 Scegli pacchetto:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("inc_"))
async def inc_pkg(callback: types.CallbackQuery, state: FSMContext):
    pkg = callback.data.split("_")[1]
    await state.update_data(inc_pkg=pkg, total=INCREMENTS_PRICES[pkg])
    await callback.message.edit_text(f"✅ Pacchetto {pkg}\n\n1. Aggiungi @GlobalStreaming2_bot come Admin.\n2. Permesso 'Invitare utenti'.\n\n🔗 Invia il LINK del canale:")
    await state.set_state(BotStates.waiting_for_increment_link)

@dp.message(BotStates.waiting_for_increment_link)
async def inc_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text)
    cau = generate_causale(message.from_user.id)
    d = await state.get_data()
    await state.update_data(causale=cau)
    await message.answer(f"💳 **PAGAMENTO**\nImporto: {d['total']}€\nCausale: `{cau}`\n\nIBAN: `{IBAN_DATI}`\n\n📸 Invia la ricevuta:")
    await state.set_state(BotStates.waiting_for_receipt)

# --- GESTIONE RICEVUTA & ADMIN ---
@dp.message(BotStates.waiting_for_receipt, F.photo)
async def get_receipt(message: types.Message, state: FSMContext):
    d = await state.get_data()
    txt = f"📩 **NUOVO ORDINE**\n👤 @{message.from_user.username}\n💰 {d['total']}€\n🔑 Causale: `{d['causale']}`"
    kb = [[types.InlineKeyboardButton(text="✅ APPROVA", callback_data=f"ap_{message.from_user.id}"),
           types.InlineKeyboardButton(text="❌ RIFIUTA", callback_data=f"re_{message.from_user.id}")]]
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=txt, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await message.answer("✅ Ricevuta inviata! Attendi conferma dell'admin.")
    await state.clear()

@dp.callback_query(F.data.startswith("ap_"))
async def approve(cb: types.CallbackQuery):
    uid = int(cb.data.split("_")[1])
    await cb.message.edit_caption(caption=cb.message.caption + "\n\n🟢 **APPROVATO**")
    await bot.send_message(uid, "🎉 Il tuo pagamento è stato confermato!")

@dp.callback_query(F.data == "user_view")
async def user_view(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(cb)

@dp.callback_query(F.data == "r_canc")
async def cancel_order(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(cb)

# --- AVVIO ---
async def main():
    # Flask in thread separato
    threading.Thread(target=run_flask, daemon=True).start()

    # Avvio Bot
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
