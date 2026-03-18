import asyncio
import logging
import aiosqlite
from datetime import date, timedelta, datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from config import DB_PATH, PROMO_CODES, SERVICES
import os

from config import BOT_TOKEN
from states import Booking, Phone
from db import (
    init_db, seed_data, get_locations, get_barbers_by_location,
    get_free_slots, get_client_by_tgid, add_or_update_client,
    set_client_phone, create_appointment, get_barber_name, get_barber_profile,
    get_appointments_for_barber, get_all_client_ids
)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def day_options():
    today = date.today()
    return [
        (today.strftime("%Y-%m-%d"), "Astăzi"),
        ((today + timedelta(days=1)).strftime("%Y-%m-%d"), "Mâine"),
        ((today + timedelta(days=2)).strftime("%Y-%m-%d"), "Poimâine"),
    ]

# Start
@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await add_or_update_client(message.from_user.id, message.from_user.full_name)
    kb = InlineKeyboardBuilder()
    kb.button(text="Rezervă o programare", callback_data="flow:start")
    kb.button(text="💰 Lista de prețuri", callback_data="show_prices")
    kb.button(text="Actualizează telefonul", callback_data="flow:phone")
    kb.adjust(1)
    await state.clear()
    await message.answer(
        "👋 Salut! Bine ai venit la MolodoyBarbershop.\nAlege o acțiune:",
        reply_markup=kb.as_markup()
    )

# Telefon
@dp.callback_query(F.data == "flow:phone")
async def ask_phone(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(Phone.waiting_phone)
    await callback.message.answer("📱 Trimite-mi numărul tău de telefon (format: +373XXXXXXXX).")

@dp.message(Phone.waiting_phone, F.text.regexp(r"^\+?\d[\d\s\-]{7,}$"))
async def save_phone(message: Message, state: FSMContext):
    await set_client_phone(message.from_user.id, message.text.strip())
    await state.clear()
    await message.answer("✅ Telefon salvat. Poți continua cu rezervarea: /start")

# список ID админов (замени на реальные Telegram ID)
ADMINS = [123456789, 987654321]

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Nu aveți acces la panoul de administrare.")
        return

    today = date.today().strftime("%Y-%m-%d")
    barbers = await get_barbers_by_location(location_id=None)  # все барберы

    kb = InlineKeyboardBuilder()
    for barber_id, barber_name in barbers:
        kb.button(text=barber_name, callback_data=f"admin:{barber_id}:{today}")
    kb.adjust(1)
    await message.answer("💈 Alegeți barberul pentru a vedea programările de astăzi:", reply_markup=kb.as_markup())

@dp.message(Command("promo"))
async def apply_promo(message: Message, state: FSMContext):
    code = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    if not code:
        await message.answer("ℹ️ Folosește: /promo COD_PROMO")
        return

    discount = PROMO_CODES.get(code.upper())
    if discount:
        await state.update_data(promo=discount)
        await message.answer(f"🎉 Cod valid! Ai {discount}% reducere la următoarea vizită.")
    else:
        await message.answer("❌ Cod promoțional invalid.")


@dp.callback_query(F.data.startswith("admin:"))
async def show_barber_appointments(callback: CallbackQuery):
    _, barber_id, date_str = callback.data.split(":")
    appointments = await get_appointments_for_barber(int(barber_id), date_str)

    if not appointments:
        await callback.message.answer("📭 Nu sunt programări.")
        return

    text = "\n".join([f"{a[2]} — {a[0]} ({a[1]})" for a in appointments])
    await callback.message.answer(f"📋 Programări pentru {date_str}:\n{text}")
    
@dp.message(Command("prices"))
async def cmd_prices(message: Message):
    text = "📋 <b>Lista de servicii și prețuri:</b>\n\n"
    for service, price in SERVICES.items():
        text += f"✂️ {service}: {price} MDL\n"
    await message.answer(text, parse_mode="HTML")

@dp.callback_query(F.data == "show_prices")
async def cb_prices(callback: CallbackQuery):
    await callback.answer()
    text = "📋 <b>Lista de servicii și prețuri:</b>\n\n"
    for service, price in SERVICES.items():
        text += f"✂️ {service}: {price} MDL\n"
    await callback.message.answer(text, parse_mode="HTML")

@dp.message(Command("broadcast"))
async def broadcast(message: Message):
    if message.from_user.id not in ADMINS:
        return

    # Extrage textul mesajului după comandă
    text = message.text.replace("/broadcast", "", 1).strip()
    if not text:
        await message.answer("ℹ️ Folosește: /broadcast <mesajul tău>")
        return

    clients = await get_all_client_ids()
    count = 0
    for user_id in clients:
        try:
            await bot.send_message(user_id, f"📢 <b>Anunț MolodoyBarbershop:</b>\n\n{text}", parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05) # Evităm spam limits
        except Exception:
            pass # Utilizatorul a blocat botul
    
    await message.answer(f"✅ Mesaj trimis cu succes la {count} utilizatori.")

@dp.message(Phone.waiting_phone)
async def invalid_phone(message: Message):
    await message.answer("Format invalid. Exemplu: +37360123456")

@dp.message(Command("mybookings"))
async def show_my_bookings(message: Message):
    client = await get_client_by_tgid(message.from_user.id)
    if not client:
        await message.answer("❌ Nu ești înregistrat. Folosește /start pentru a începe.")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT date, time, barber_id FROM appointments WHERE client_name=? ORDER BY date, time",
            (client[2],)
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        await message.answer("📭 Nu ai programări active.")
        return

    text = "📋 Programările tale:\n"
    for date_str, time_str, barber_id in rows:
        barber_name = await get_barber_name(barber_id)
        text += f"• {date_str} la {time_str} cu {barber_name}\n"

    await message.answer(text)

@dp.message(Command("cancel"))
async def cancel_booking(message: Message):
    client = await get_client_by_tgid(message.from_user.id)
    if not client:
        await message.answer("❌ Nu ești înregistrat.")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, date, time, barber_id FROM appointments WHERE client_name=? ORDER BY date, time",
            (client[2],)
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        await message.answer("📭 Nu ai programări active.")
        return

    kb = InlineKeyboardBuilder()
    text = "📋 Programările tale:\n"
    for appt_id, date_str, time_str, barber_id in rows:
        barber_name = await get_barber_name(barber_id)
        text += f"• {date_str} la {time_str} cu {barber_name}\n"
        kb.button(text=f"❌ {date_str} {time_str}", callback_data=f"cancel:{appt_id}")
    kb.adjust(1)

    await message.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("cancel:"))
async def confirm_cancel(callback: CallbackQuery):
    appt_id = int(callback.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM appointments WHERE id=?", (appt_id,))
        await db.commit()

    await callback.message.answer("✅ Programarea a fost anulată.")
    await callback.answer()

@dp.message(Command("addphoto"))
async def add_photo(message: Message):
    if message.from_user.id not in ADMINS:
        await message.answer("⛔ Nu ai drepturi de admin.")
        return

    if not message.photo:
        await message.answer("📷 Trimite o fotografie împreună cu comanda /addphoto.")
        return

    # ia cea mai bună rezoluție
    photo = message.photo[-1]
    file_path = f"images/{photo.file_id}.jpg"
    os.makedirs("images", exist_ok=True)
    await bot.download(photo, destination=file_path)

    await message.answer("✅ Fotografia a fost adăugată în galerie!")

@dp.message(Command("gallery"))
async def show_gallery(message: Message):
    if not os.path.exists("images"):
        await message.answer("📭 Galeria este goală.")
        return

    files = os.listdir("images")
    if not files:
        await message.answer("📭 Galeria este goală.")
        return

    await message.answer("📸 Exemple de lucrări MolodoyBarbershop:")
    for f in files[:5]:  # trimite primele 5 imagini
        await message.answer_photo(FSInputFile(f"images/{f}"))

# Flow rezervare: locație
@dp.callback_query(F.data == "flow:start")
async def choose_location(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    locations = await get_locations()
    kb = InlineKeyboardBuilder()
    for loc_id, loc_name in locations:
        kb.button(text=loc_name, callback_data=f"loc:{loc_id}")
    kb.adjust(1)
    await state.set_state(Booking.choosing_location)
    await callback.message.answer("📍 Alege locația:", reply_markup=kb.as_markup())

@dp.callback_query(Booking.choosing_location, F.data.startswith("loc:"))
async def choose_barber(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    location_id = int(callback.data.split(":")[1])
    await state.update_data(location_id=location_id)

    barbers = await get_barbers_by_location(location_id)
    if not barbers:
        await callback.message.answer("Nu sunt barberii definiți pentru această locație încă.")
        return

    kb = InlineKeyboardBuilder()
    for barber_id, barber_name in barbers:
        kb.button(text=barber_name, callback_data=f"barber:{barber_id}")
    kb.adjust(1)
    await state.set_state(Booking.choosing_barber)
    await callback.message.answer("💈 Alege barberul:", reply_markup=kb.as_markup())

@dp.callback_query(Booking.choosing_barber, F.data.startswith("barber:"))
async def choose_day(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(Booking.choosing_day)
    barber_id = int(callback.data.split(":")[1])
    await state.update_data(barber_id=barber_id)

    # --- NEW: Show barber profile ---
    profile = await get_barber_profile(barber_id)
    profile_text = ""
    if profile:
        name, exp, spec = profile
        exp_text = f"\n📅 Experiență: {exp}" if exp else ""
        spec_text = f"\n✂️ Specializare: {spec}" if spec else ""
        profile_text = f"Ați ales barberul:\n\n*👨‍🔧 {name}*{exp_text}{spec_text}\n\n"

    kb = InlineKeyboardBuilder()
    for dval, dlabel in day_options():
        kb.button(text=dlabel, callback_data=f"day:{dval}")
    kb.adjust(3)
    await callback.message.edit_text(
        f"{profile_text}🗓 Alegeți ziua:",
        reply_markup=kb.as_markup(),
        parse_mode="MarkdownV2"
    )

@dp.callback_query(Booking.choosing_day, F.data.startswith("day:"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    chosen_date = callback.data.split(":")[1]
    await state.update_data(date=chosen_date)

    data = await state.get_data()
    barber_id = data.get("barber_id")
    free = await get_free_slots(barber_id, chosen_date)

    if not free:
        await callback.message.answer("Nu mai sunt sloturi libere pentru data aleasă. Alege altă zi.")
        return

    kb = InlineKeyboardBuilder()
    for t in free:
        kb.button(text=t, callback_data=f"time:{t}")
    kb.adjust(3)
    await state.set_state(Booking.choosing_time)
    await callback.message.answer(f"🕒 Alege ora pentru {chosen_date}:", reply_markup=kb.as_markup())

@dp.callback_query(Booking.choosing_time, F.data.startswith("time:"))
async def confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    chosen_time = callback.data.split(":")[1]
    await state.update_data(time=chosen_time)

    data = await state.get_data()
    barber_id = data["barber_id"]
    chosen_date = data["date"]
    barber_name = await get_barber_name(barber_id)
    client = await get_client_by_tgid(callback.from_user.id)

    client_name = client[2] if client else callback.from_user.full_name
    phone = client[3] if client and client[3] else "—"

    text = (
        f"Confirmezi programarea?\n\n"
        f"• Barber: {barber_name} (ID {barber_id})\n"
        f"• Data: {chosen_date}\n"
        f"• Ora: {chosen_time}\n"
        f"• Nume: {client_name}\n"
        f"• Telefon: {phone}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="Confirmă ✅", callback_data="confirm")
    kb.button(text="Anulează ❌", callback_data="cancel")
    kb.adjust(2)
    await state.set_state(Booking.confirming)
    await callback.message.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(Booking.confirming, F.data == "confirm")
async def finalize(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    barber_id = data["barber_id"]
    chosen_date = data["date"]
    chosen_time = data["time"]
    promo = data.get("promo")

    # Final check to prevent double booking
    free = await get_free_slots(barber_id, chosen_date)
    if chosen_time not in free:
        await callback.message.edit_text(
            "⚠️ Ne pare rău, acest interval orar a fost ocupat chiar acum. "
            "Te rugăm să reîncepi procesul folosind /start."
        )
        await state.clear()
        return

    client = await get_client_by_tgid(callback.from_user.id)
    client_name = client[2] if client else callback.from_user.full_name
    phone = client[3] if client and client[3] else ""

    await create_appointment(barber_id, client_name, phone, chosen_date, chosen_time)

    # Prepare final confirmation message
    final_message = f"✅ Programare creată pentru {chosen_date} la {chosen_time}. Mulțumim!"
    if promo:
        final_message += f"\n🎉 Reducerea ta de {promo}% a fost aplicată."

    await callback.message.edit_text(final_message)

    # Schedule a reminder
    asyncio.create_task(schedule_reminder(callback.from_user.id, chosen_date, chosen_time))
    await state.clear()

@dp.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer("❌ Programarea a fost anulată. Poți reîncepe cu /start.")

# --- Reminder function ---
async def schedule_reminder(user_id: int, date_str: str, time_str: str):
    visit_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    remind_dt = visit_dt - timedelta(hours=1)
    delay = (remind_dt - datetime.now()).total_seconds()

    if delay > 0:
        await asyncio.sleep(delay)
        await bot.send_message(user_id, f"⏰ Memento: aveți o programare astăzi la {time_str}!")

# Run
async def main():
    await init_db()
    await seed_data()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())