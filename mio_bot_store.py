import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- CONFIGURAZIONE ---
TOKEN = "8660149890:AAGtywvvWPtDGrnd3RQ6ODz7jBKXbYCafVc"
ADMIN_ID = 8361466889

# --- LISTINO PREZZI ---
PRICES = {
    "sponsor_24h": "15€",
    "sponsor_48h": "25€",
    "inc_1000": "10€",
    "inc_5000": "40€"
}

# --- STATI PRENOTAZIONE ---
class Booking(StatesGroup):
    choosing_service = State()
    choosing_date = State()
    choosing_time = State()
    choosing_payment = State()
    waiting_screenshot = State()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect('store.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT)')
    conn.commit()
    conn.close()

init_db()

# --- SERVER PER RENDER ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Online"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- TASTIERE ---
def main_menu():
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="💎 Sponsor Canale", callback_data="buy_sponsor"))
    kb.row(types.InlineKeyboardButton(text="📈 Incrementi Social", callback_data="buy_inc"))
    kb.row(types.InlineKeyboardButton(text="📞 Supporto", url="https://t.me/GlobalSportsContatto"))
    return kb.as_markup()

def payment_menu():
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="💳 Carta / PayPal", callback_data="pay_paypal"))
    kb.row(types.InlineKeyboardButton(text="₿ Crypto (LTC/BTC)", callback_data="pay_crypto"))
    return kb.as_markup()

# --- LOGICA ---
@dp.message(Command("start"))
async def start(message: types.Message):
    # Salva utente
    conn = sqlite3.connect('store.db')
    conn.execute("INSERT OR IGNORE INTO users VALUES (?,?)", (message.from_user.id, message.from_user.username))
    conn.commit()
    conn.close()

    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text="📊 Stats", callback_data="admin_stats"))
        kb.row(types.InlineKeyboardButton(text="🛒 Vista Utente", callback_data="user_view"))
        await message.answer("🛠 **PANNELLO ADMIN**", reply_markup=kb.as_markup())
    else:
        await message.answer(f"👋 Ciao {message.from_user.first_name}!\nBenvenuto in **Global Sports Ads**.\nScegli cosa desideri:", reply_markup=main_menu())

@dp.callback_query(F.data == "buy_sponsor")
async def process_sponsor(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text=f"Sponsor 24h - {PRICES['sponsor_24h']}", callback_data="set_sponsor_24h"))
    kb.row(types.InlineKeyboardButton(text=f"Sponsor 48h - {PRICES['sponsor_48h']}", callback_data="set_sponsor_48h"))
    await callback.message.edit_text("Seleziona la durata dello sponsor:", reply_markup=kb.as_markup())
    await state.set_state(Booking.choosing_date)

@dp.callback_query(F.data.startswith("set_sponsor"))
async def process_date(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(service=callback.data, price=PRICES[callback.data.replace("set_", "")])

    # Crea calendario (prossimi 5 giorni)
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        date_str = (datetime.now() + timedelta(days=i)).strftime("%d/%m")
        kb.row(types.InlineKeyboardButton(text=date_str, callback_data=f"date_{date_str}"))

    await callback.message.edit_text("📅 **Seleziona il giorno:**", reply_markup=kb.as_markup())
    await state.set_state(Booking.choosing_time)

@dp.callback_query(F.data.startswith("date_"))
async def process_time(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(date=callback.data.replace("date_", ""))

    kb = InlineKeyboardBuilder()
    ore = ["10:00", "14:00", "18:00", "21:00"]
    for ora in ore:
        kb.add(types.InlineKeyboardButton(text=ora, callback_data=f"time_{ora}"))

    await callback.message.edit_text("⏰ **A che ora vuoi pubblicare?**", reply_markup=kb.as_markup())
    await state.set_state(Booking.choosing_payment)

@dp.callback_query(F.data.startswith("time_"))
async def process_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(time=callback.data.replace("time_", ""))
    data = await state.get_data()

    text = (f"📝 **RECAP ORDINE**\n\n"
            f"🔹 Servizio: {data['service']}\n"
            f"📅 Data: {data['date']}\n"
            f"⏰ Ora: {data['time']}\n"
            f"💰 Totale: {data['price']}\n\n"
            f"Seleziona il metodo di pagamento:")

    await callback.message.edit_text(text, reply_markup=payment_menu())
    await state.set_state(Booking.waiting_screenshot)

@dp.callback_query(F.data.startswith("pay_"))
async def instruct_payment(callback: types.CallbackQuery, state: FSMContext):
    method = "PayPal/Carta" if "paypal" in callback.data else "Crypto"
    await callback.message.answer(f"✅ Hai scelto {method}.\n\nInvia il pagamento a: `tuo_account@email.com`\n\n**Dopo aver pagato, invia qui lo SCREENSHOT della ricevuta.**")

@dp.message(Booking.waiting_screenshot, F.photo)
async def handle_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user

    # Messaggio a TE (ADMIN)
    admin_text = (f"🚨 **NUOVO ORDINE RICEVUTO!**\n\n"
                  f"👤 Utente: @{user.username} (ID: {user.id})\n"
                  f"📦 Servizio: {data['service']}\n"
                  f"📅 Data: {data['date']} alle {data['time']}\n"
                  f"💰 Prezzo: {data['price']}\n\n"
                  f"Controlla lo screenshot qui sopra e conferma!")

    await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=admin_text)
    await message.answer("✅ Ricevuto! L'admin controllerà lo screenshot e ti contatterà a breve.")
    await state.clear()

@dp.callback_query(F.data == "user_view")
async def user_view(callback: types.CallbackQuery):
    await callback.message.answer("Ecco la vista utente:", reply_markup=main_menu())
    await callback.answer()

async def main():
    Thread(target=run_flask).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
