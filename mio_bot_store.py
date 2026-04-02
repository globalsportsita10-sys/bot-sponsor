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
API_TOKEN = '8513979649:AAHceiZHqQDqU5gRVhILGD2WMC9OfevT7kw' # <-- METTI IL TOKEN GIUSTO QUI
ADMIN_ID = 8361466889
IBAN_DATI = "IT 00 X 00000 00000 000000000000"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- DATI ---
CHANNELS_DATA = {
    "goal": {"name": "Goal Highlights ⚽️", "price_per_h": 2.0},
    "juve": {"name": "Juventus Planet ⚪️⚫️", "price_per_h": 1.5},
}
for i in range(1, 10):
    CHANNELS_DATA[f"str_{i}"] = {"name": f"Streaming {i} 📺", "price_per_h": 1.0}

EXTRAS_DATA = {
    "pin": {"name": "📌 Pin nel Canale", "price": 5},
    "nodel": {"name": "🚫 Nessuna Eliminazione", "price": 10}
}

INCREMENTS_PRICES = {"1K": 50, "2K": 80, "3K": 120, "5K": 200}

# --- STATI FSM ---
class SponsorFlow(StatesGroup):
    channels = State()
    duration = State()
    custom_duration = State()
    extras = State()
    date = State()
    start_time = State()
    custom_time = State()
    receipt = State()

# --- UTILS ---
def generate_causale(user_id):
    rc = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ADV-{user_id}-{rc}"

def calc_total(data):
    # Calcolo base: (Prezzo canali * ore) + Extras
    tot = 0
    hours = int(data.get('duration', 0))
    for ch in data.get('channels', []):
        tot += CHANNELS_DATA[ch]['price_per_h'] * hours
    for ex in data.get('extras', []):
        tot += EXTRAS_DATA[ex]['price']
    return tot

# --- MENU PRINCIPALE ---
async def show_main_menu(obj):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="📢 Acquista Sponsor", callback_data="buy_sponsor"))
    kb.row(types.InlineKeyboardButton(text="🚀 Acquista Incrementi", callback_data="buy_increment"))
    kb.row(types.InlineKeyboardButton(text="🆘 Assistenza", url="https://t.me/GlobalSportsContatto"))

    txt = "👋 **Benvenuto nel Global Advertising Bot!**\nScegli un'opzione:"
    if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=kb.as_markup())
    else: await obj.message.edit_text(txt, reply_markup=kb.as_markup())

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardBuilder()
        kb.row(types.InlineKeyboardButton(text="🛒 Vista Utente", callback_data="user_view"))
        await message.answer("🛠 **PANNELLO ADMIN**", reply_markup=kb.as_markup())
    else:
        await show_main_menu(message)

@dp.callback_query(F.data == "user_view")
async def user_view(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(callback)

# ==========================================
# FLUSSO SPONSOR
# ==========================================

# 1. CANALI
@dp.callback_query(F.data == "buy_sponsor")
async def sp_step1_channels(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(channels=[])
    await render_channels(callback, [])
    await state.set_state(SponsorFlow.channels)

async def render_channels(callback, sel_chans):
    kb = InlineKeyboardBuilder()
    for k, v in CHANNELS_DATA.items():
        kb.row(types.InlineKeyboardButton(text=f"{'✅' if k in sel_chans else '◻️'} {v['name']}", callback_data=f"ch_{k}"))

    kb.row(types.InlineKeyboardButton(text="✅ Seleziona Tutti", callback_data="ch_all"))
    kb.row(
        types.InlineKeyboardButton(text="⬅️ Menu", callback_data="user_view"),
        types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_dur")
    )
    txt = "📺 **PASSO 1: Scegli i Canali**\nSeleziona dove vuoi pubblicare:"
    await callback.message.edit_text(txt, reply_markup=kb.as_markup())

@dp.callback_query(SponsorFlow.channels, F.data.startswith("ch_"))
async def handle_channels(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.replace("ch_", "")
    data = await state.get_data()
    sel = data.get('channels', [])

    if action == "all":
        sel = list(CHANNELS_DATA.keys())
    elif action in sel:
        sel.remove(action)
    else:
        sel.append(action)

    await state.update_data(channels=sel)
    await render_channels(callback, sel)

# 2. DURATA ORE
@dp.callback_query(SponsorFlow.channels, F.data == "go_dur")
async def sp_step2_duration(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('channels'):
        return await callback.answer("⚠️ Seleziona almeno un canale!", show_alert=True)

    kb = InlineKeyboardBuilder()
    for h in [3, 6, 12, 24]:
        kb.add(types.InlineKeyboardButton(text=f"{h} Ore", callback_data=f"dur_{h}"))
    kb.adjust(2)
    kb.row(types.InlineKeyboardButton(text="✍️ Ore Personalizzate", callback_data="dur_custom"))
    kb.row(
        types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="buy_sponsor"),
        types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_extras")
    )

    txt = f"⏳ **PASSO 2: Durata**\nHai scelto {len(data['channels'])} canali.\nSeleziona o scrivi quante ore deve rimanere il post:"
    await callback.message.edit_text(txt, reply_markup=kb.as_markup())
    await state.set_state(SponsorFlow.duration)

@dp.callback_query(SponsorFlow.duration, F.data.startswith("dur_"))
async def handle_dur(callback: types.CallbackQuery, state: FSMContext):
    val = callback.data.replace("dur_", "")
    if val == "custom":
        await callback.message.edit_text("✍️ **Scrivi in chat il numero di ore** (es: 48):")
        await state.set_state(SponsorFlow.custom_duration)
    else:
        await state.update_data(duration=int(val))
        await callback.answer(f"✅ Impostato a {val} ore")

@dp.message(SponsorFlow.custom_duration)
async def handle_custom_dur(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("⚠️ Inserisci solo un numero valido (es: 48).")
    await state.update_data(duration=int(message.text))
    # Riporta al menu durata ma aggiornato (simuliamo bottone avanti)
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_extras"))
    await message.answer(f"✅ Hai impostato {message.text} ore.\nClicca Avanti per procedere:", reply_markup=kb.as_markup())
    await state.set_state(SponsorFlow.duration)

# 3. AGGIUNTE (EXTRAS)
@dp.callback_query(SponsorFlow.duration, F.data == "go_extras")
async def sp_step3_extras(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if 'duration' not in data:
        return await callback.answer("⚠️ Scegli prima la durata!", show_alert=True)

    if 'extras' not in data: await state.update_data(extras=[])
    data = await state.get_data() # ricarica
    await render_extras(callback, data.get('extras', []))
    await state.set_state(SponsorFlow.extras)

async def render_extras(callback, sel_extras):
    kb = InlineKeyboardBuilder()
    for k, v in EXTRAS_DATA.items():
        kb.row(types.InlineKeyboardButton(text=f"{'✅' if k in sel_extras else '◻️'} {v['name']} (+{v['price']}€)", callback_data=f"ex_{k}"))

    kb.row(
        types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="go_dur"), # Torna a durata (bisognerà gestire il ricaricamento)
        types.InlineKeyboardButton(text="Avanti ➡️", callback_data="go_date")
    )
    await callback.message.edit_text("✨ **PASSO 3: Aggiunte (Opzionale)**\nVuoi dei servizi extra?", reply_markup=kb.as_markup())

@dp.callback_query(SponsorFlow.extras, F.data.startswith("ex_"))
async def handle_extras(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.replace("ex_", "")
    data = await state.get_data()
    sel = data.get('extras', [])
    if action in sel: sel.remove(action)
    else: sel.append(action)
    await state.update_data(extras=sel)
    await render_extras(callback, sel)

# 4. DATA
@dp.callback_query(SponsorFlow.extras, F.data == "go_date")
async def sp_step4_date(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for i in range(0, 5):
        d = (datetime.now() + timedelta(days=i)).strftime("%d/%m/%Y")
        kb.add(types.InlineKeyboardButton(text=d, callback_data=f"dt_{d}"))
    kb.adjust(2)
    kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="go_extras_back"))
    await callback.message.edit_text("📅 **PASSO 4: Data**\nScegli il giorno della pubblicazione:", reply_markup=kb.as_markup())
    await state.set_state(SponsorFlow.date)

@dp.callback_query(F.data == "go_extras_back") # Helper per tornare indietro
async def back_to_ex(callback: types.CallbackQuery, state: FSMContext):
    await sp_step3_extras(callback, state)

@dp.callback_query(SponsorFlow.date, F.data.startswith("dt_"))
async def handle_date(callback: types.CallbackQuery, state: FSMContext):
    dt = callback.data.replace("dt_", "")
    await state.update_data(date=dt)

    # 5. ORA DI INIZIO
    kb = InlineKeyboardBuilder()
    for t in ["10:00", "14:00", "18:00", "21:00"]:
        kb.add(types.InlineKeyboardButton(text=t, callback_data=f"tm_{t}"))
    kb.adjust(2)
    kb.row(types.InlineKeyboardButton(text="✍️ Ora Personalizzata", callback_data="tm_custom"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Indietro", callback_data="go_date"))

    await callback.message.edit_text("⏰ **PASSO 5: Ora di inizio**\nA che ora pubblichiamo?", reply_markup=kb.as_markup())
    await state.set_state(SponsorFlow.start_time)

@dp.callback_query(SponsorFlow.start_time, F.data.startswith("tm_"))
async def handle_time(callback: types.CallbackQuery, state: FSMContext):
    val = callback.data.replace("tm_", "")
    if val == "custom":
        await callback.message.edit_text("✍️ **Scrivi in chat l'orario** (es: 15:30):")
        await state.set_state(SponsorFlow.custom_time)
    else:
        await state.update_data(start_time=val)
        await show_cart(callback, state)

@dp.message(SponsorFlow.custom_time)
async def handle_custom_time(message: types.Message, state: FSMContext):
    await state.update_data(start_time=message.text)
    # Mostriamo direttamente il carrello passando il message come se fosse la callback
    await show_cart(message, state)

# 6. CARRELLO (RECAP)
async def show_cart(obj, state: FSMContext):
    data = await state.get_data()
    tot = calc_total(data)
    cau = generate_causale(obj.from_user.id)
    await state.update_data(total=tot, causale=cau)

    ch_names = [CHANNELS_DATA[c]['name'] for c in data['channels']]
    ex_names = [EXTRAS_DATA[e]['name'] for e in data.get('extras', [])]

    txt = (f"🛒 **CARRELLO E RIEPILOGO**\n\n"
           f"📺 **Canali ({len(ch_names)}):**\n- " + "\n- ".join(ch_names) + "\n"
           f"⏳ **Durata:** {data['duration']} Ore\n"
           f"✨ **Aggiunte:** {', '.join(ex_names) if ex_names else 'Nessuna'}\n"
           f"📅 **Data e Ora:** {data['date']} alle {data['start_time']}\n\n"
           f"💰 **TOTALE:** {tot}€\n"
           f"🔑 **Causale:** `{cau}`\n\n"
           f"Se tutto è corretto, procedi al pagamento.")

    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="💳 Procedi al Pagamento", callback_data="pay_now"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Annulla e Ricomincia", callback_data="user_view"))

    if isinstance(obj, types.Message): await obj.answer(txt, reply_markup=kb.as_markup())
    else: await obj.message.edit_text(txt, reply_markup=kb.as_markup())
    await state.set_state(SponsorFlow.receipt)

# 7. PAGAMENTO E RICEVUTA
@dp.callback_query(SponsorFlow.receipt, F.data == "pay_now")
async def req_receipt(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    txt = (f"💳 **PAGAMENTO**\n\n"
           f"Importo: **{data['total']}€**\n"
           f"IBAN: `{IBAN_DATI}`\n"
           f"Causale Obbligatoria: `{data['causale']}`\n\n"
           f"📸 **Invia qui sotto lo screenshot della ricevuta per confermare.**")
    await callback.message.edit_text(txt)

@dp.message(SponsorFlow.receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    u = message.from_user

    adm_txt = (f"🚨 **NUOVO ORDINE SPONSOR**\n\n"
               f"👤 Da: @{u.username}\n"
               f"💰 Totale: {data['total']}€\n"
               f"🔑 Causale: `{data['causale']}`\n\n"
               f"Controlla lo screenshot.")

    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="✅ Approva", callback_data=f"ok_{u.id}"),
        types.InlineKeyboardButton(text="❌ Rifiuta", callback_data=f"no_{u.id}")
    )

    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=adm_txt, reply_markup=kb.as_markup())
    await message.answer("✅ Ricevuta inviata! L'admin confermerà a breve l'attivazione.")
    await state.clear()

# --- AVVIO ---
async def main():
    Thread(target=run_flask, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
