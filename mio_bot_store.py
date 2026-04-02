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
def home():
    return "Bot is Running!"

def run_flask():
    # Porta impostata a 10000 come richiesto
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURAZIONE BOT ---
API_TOKEN = '8660149890:AAFPeMsPAbbFjZID012-NXXyUNGyDaF2gLU'
ADMIN_ID = 8361466889

IBAN_DATI = "IT 00 X 00000 00000 000000000000"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

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
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_increment_link = State()
    waiting_for_receipt = State()

# --- FUNZIONI UTILS ---
def generate_causale(user_id):
    rc = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ADV-{user_id}-{rc}"

def calculate_total(selected_keys, hours):
    total = 0
    str_count = sum(1 for k in selected_keys if "str_" in k)
    prices_str = {3: 6, 6: 9.5, 12: 15, 24: 19.5}

    if str_count == 9: total += {3: 25, 6: 35, 12: 50, 24: 65}[hours]
    elif 5 <= str_count <= 8: total += {3: 20, 6: 30, 12: 40, 24: 50}[hours]
    elif 3 <= str_count <= 4: total += {3: 15, 6: 20, 12: 35, 24: 45}[hours]
    else: total += (str_count * prices_str[hours])

    if "goal" in selected_keys: total += {3: 5, 6: 7.5, 12: 11, 24: 13.5}[hours]
    if "juve" in selected_keys: total += {3: 4, 6: 5.5, 12: 8, 24: 12}[hours]
    return total

# --- MENU PRINCIPALE ---
async def show_main_menu(message_or_call):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📢 Acquista Sponsor", callback_data="buy_sponsor"))
    builder.row(types.InlineKeyboardButton(text="🚀 Acquista Incrementi", callback_data="buy_increment"))
    builder.row(
        types.InlineKeyboardButton(text="🔍 Stato Ordine", callback_data="check_status"),
        types.InlineKeyboardButton(text="📋 Listino", url="https://t.me/GlobalSportsSponsor")
    )
    builder.row(types.InlineKeyboardButton(text="🆘 Assistenza", url="https://t.me/GlobalSportsContatto"))

    text = "👋 **Benvenuto nel Global Advertising Bot!**\nScegli un'opzione qui sotto:"

    if isinstance(message_or_call, types.Message):
        await message_or_call.answer(text, reply_markup=builder.as_markup())
    else:
        await message_or_call.message.edit_text(text, reply_markup=builder.as_markup())

# --- HANDLERS ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id == ADMIN_ID:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📊 Statistiche", callback_data="admin_stats"))
        builder.row(types.InlineKeyboardButton(text="🛒 Vista Utente", callback_data="user_view"))
        await message.answer("🛠 **PANNELLO ADMIN**", reply_markup=builder.as_markup())
    else:
        await show_main_menu(message)

@dp.callback_query(F.data == "user_view")
async def user_view(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(callback)

# --- LOGICA SPONSOR ---
@dp.callback_query(F.data == "buy_sponsor")
async def sponsor_init(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Invia il post da sponsorizzare (Testo, Foto o Video):")
    await state.set_state(BotStates.waiting_for_content)

@dp.message(BotStates.waiting_for_content)
async def get_content(message: types.Message, state: FSMContext):
    await state.update_data(msg_id=message.message_id, sel_chans=[])
    await show_chan_sel(message, [])
    await state.set_state(BotStates.waiting_for_channels)

async def show_chan_sel(msg, sel):
    builder = InlineKeyboardBuilder()
    for k, v in CHANNELS_DATA.items():
        builder.row(types.InlineKeyboardButton(text=f"{'✅' if k in sel else '◻️'} {v['name']}", callback_data=f"sel_{k}"))
    if sel:
        builder.row(types.InlineKeyboardButton(text="➡️ Prosegui", callback_data="chans_ok"))

    text = "📺 **Seleziona i canali:**"
    if isinstance(msg, types.Message):
        await msg.answer(text, reply_markup=builder.as_markup())
    else:
        await msg.message.edit_reply_markup(reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("sel_"), BotStates.waiting_for_channels)
async def toggle_ch(callback: types.CallbackQuery, state: FSMContext):
    k = callback.data.split("_")[1]
    data = await state.get_data()
    sel = data.get('sel_chans', [])
    if k in sel: sel.remove(k)
    else: sel.append(k)
    await state.update_data(sel_chans=sel)
    await show_chan_sel(callback, sel)

@dp.callback_query(F.data == "chans_ok", BotStates.waiting_for_channels)
async def dur_sel(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    for h in [3, 6, 12, 24]:
        builder.add(types.InlineKeyboardButton(text=f"{h}h", callback_data=f"h_{h}"))
    await callback.message.edit_text("⏳ **Scegli la durata della permanenza:**", reply_markup=builder.as_markup())
    await state.set_state(BotStates.waiting_for_duration)

@dp.callback_query(F.data.startswith("h_"), BotStates.waiting_for_duration)
async def time_sel_start(callback: types.CallbackQuery, state: FSMContext):
    h = int(callback.data.split("_")[1])
    data = await state.get_data()
    tot = calculate_total(data['sel_chans'], h)
    cau = generate_causale(callback.from_user.id)
    await state.update_data(total=tot, causale=cau, hours=h)

    await callback.message.answer(f"💳 **PAGAMENTO**\n\nImporto: **{tot}€**\nCausale: `{cau}`\n\nIBAN: `{IBAN_DATI}`\n\n📸 Invia lo screenshot della ricevuta:")
    await state.set_state(BotStates.waiting_for_receipt)

# --- GESTIONE RICEVUTA ---
@dp.message(BotStates.waiting_for_receipt, F.photo)
async def receipt_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user

    admin_txt = (f"🚨 **NUOVO ORDINE**\n\n"
                 f"👤 Utente: @{user.username}\n"
                 f"💰 Totale: {data['total']}€\n"
                 f"🔑 Causale: `{data['causale']}`\n"
                 f"📦 Servizio: {data.get('inc_pkg', 'Sponsor')}")

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="✅ Approva", callback_data=f"ap_{user.id}"))
    builder.row(types.InlineKeyboardButton(text="❌ Rifiuta", callback_data=f"re_{user.id}"))

    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_txt, reply_markup=builder.as_markup())
    await message.answer("✅ Ricevuta inviata! L'admin confermerà a breve.")
    await state.clear()

@dp.callback_query(F.data.startswith("ap_"))
async def admin_approve(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(user_id, "🎉 Il tuo pagamento è stato confermato! Il tuo ordine è in elaborazione.")
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n🟢 **APPROVATO**")

# --- AVVIO ---
async def main():
    # Thread Flask per Render (Porta 10000)
    Thread(target=run_flask, daemon=True).start()

    # Avvio Bot
    logging.info("Bot in fase di avvio...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot spento.")
