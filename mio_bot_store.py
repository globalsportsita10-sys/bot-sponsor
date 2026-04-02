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

# --- CONFIGURAZIONE WEB PER RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    # LEGGE LA PORTA DA RENDER (DI SOLITO 10000) O USA LA 8080 SE LOCALE
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURAZIONE BOT ---
API_TOKEN = '8660149890:AAGtywvvWPtDGrnd3RQ6ODz7jBKXbYCafVc'
ADMIN_ID = 8361466889

IBAN_DATI = "IT 00 X 00000 00000 000000000000"
SUMUP_LINK = "https://link.sumup.it/tuolink"

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

# --- STATI E DATI ---
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

    txt = "👋 **Benvenuto nel Global Advertising Bot!**\n\nSeleziona un'opzione per iniziare."
    if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=builder.as_markup())
    else: await obj.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await show_main_menu(message)

@dp.callback_query(F.data == "user_view")
async def back_home(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(cb)

# --- FLUSSO INCREMENTI ---
@dp.callback_query(F.data == "buy_increment")
async def inc_start(cb: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    for k, v in INCREMENTS_PRICES.items(): kb.row(types.InlineKeyboardButton(text=f"🚀 {k} - {v}€", callback_data=f"inc_{k}"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Menu", callback_data="user_view"))
    await cb.message.edit_text("🚀 Scegli il pacchetto:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("inc_"))
async def inc_sel(cb: types.CallbackQuery, state: FSMContext):
    pkg = cb.data.split("_")[1]
    await state.update_data(pkg=pkg, total=INCREMENTS_PRICES[pkg])
    await cb.message.edit_text(f"✅ Hai scelto {pkg}.\n\n🔗 Invia il LINK del canale (Assicurati che il bot sia Admin):")
    await state.set_state(BotStates.waiting_for_increment_link)

@dp.message(BotStates.waiting_for_increment_link)
async def get_link(msg: types.Message, state: FSMContext):
    await state.update_data(link=msg.text, causale=f"INC-{msg.from_user.id}")
    d = await state.get_data()
    txt = f"💳 **PAGAMENTO**\nImporto: {d['total']}€\nCausale: `{d['causale']}`\n\nIBAN: `{IBAN_DATI}`\n\n📸 Invia lo screenshot della ricevuta:"
    await msg.answer(txt)
    await state.set_state(BotStates.waiting_for_receipt)

@dp.message(BotStates.waiting_for_receipt, F.photo)
async def get_receipt(msg: types.Message, state: FSMContext):
    d = await state.get_data()
    await bot.send_photo(ADMIN_ID, msg.photo[-1].file_id, caption=f"📩 **NUOVO ORDINE**\n👤 @{msg.from_user.username}\n💰 {d.get('total')}€\n🔑 Causale: `{d.get('causale')}`")
    await msg.answer("✅ Ricevuta inviata! L'admin verificherà a breve.")
    await state.clear()

# --- AVVIO ---
async def main():
    # AVVIA FLASK IN UN FILO SEPARATO
    threading.Thread(target=run_flask, daemon=True).start()

    # AVVIA IL BOT
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
