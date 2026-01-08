import asyncio
from datetime import date, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import BOT_TOKEN
from db import (
    init_db, seed_data, get_locations, get_barbers_by_location,
    get_free_slots, create_appointment, add_or_update_client,
    get_client_by_tgid, set_client_phone
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Utilitare ---
def day_options():
    today = date.today()
    return [
        (today.strftime("%Y-%m-%d"), "Astăzi"),
        ((today + timedelta(days=1)).strftime("%Y-%m-%d"), "Mâine"),
        ((today + timedelta(days=2)).strftime("%Y-%m-%d"), "Poimâine"),
    ]

# --- Start ---
@dp.message(Command("start"))
async def start(message: Message):
    await add_or_update_client(message.from_user.id, message.from_user.full_name)
    kb = InlineKeyboardBuilder()
    kb.button(text="Rezervă o programare", callback_data="flow:start")
    kb.button(text="Actualizează telefonul", callback_data="flow:phone")
    kb.adjust(1)
    await message.answer(
        "👋 Salut! Bine ai venit la MolodoyBarbershop.\n"
        "Alege o acțiune de mai jos.",
        reply_markup=kb.as_markup()
    )

# --- Telefon ---
@dp.callback_query(F.data == "flow:phone")
async def ask_phone(callback: CallbackQuery):
    await callback.message.answer("📱 Trimite-mi numărul tău de telefon (format: +373XXXXXXX).")
    await callback.answer()

@dp.message(F.text.regexp(r"^\+?\d[\d\s\-]{7,}$"))
async def save_phone(message: Message):
    await set_client_phone(message.from_user.id, message.text.strip())
    await message.answer("✅ Telefon salvat. Poți continua cu rezervarea: /start")

# --- Flow rezervare ---
@dp.callback_query(F.data == "flow:start")
async def choose_location(callback: CallbackQuery):
    locations = await get_locations()
    kb = InlineKeyboardBuilder()
    for loc_id, loc_name in locations:
        kb.button(text=loc_name, callback_data=f"loc:{loc_id}")
    kb.adjust(1)
    await callback.message.answer("📍 Alege locația:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("loc:"))
async def choose_barber(callback: CallbackQuery):
    location_id = int(callback.data.split(":")[1])
    barbers = await get_barbers_by_location(location_id)
    if not barbers:
        await callback.message.answer("Nu sunt barberii definiți pentru această locație încă.")
        await callback.answer()
        return
    kb = InlineKeyboardBuilder()
    for barber_id, barber_name in barbers:
        kb.button(text=barber_name, callback_data=f"barber:{barber_id}")
    kb.adjust(1)
    await callback.message.answer("💈 Alege barberul:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("barber:"))
async def choose_day(callback: CallbackQuery):
    barber_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardBuilder()
    for dval, dlabel in day_options():
        kb.button(text=dlabel, callback_data=f"day:{barber_id}:{dval}")
    kb.adjust(3)
    await callback.message.answer("🗓 Alege ziua:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("day:"))
async def choose_slot(callback: CallbackQuery):
    _, barber_id, chosen_date = callback.data.split(":")
    barber_id = int(barber_id)
    free = await get_free_slots(barber_id, chosen_date)
    if not free:
        await callback.message.answer("Nu mai sunt sloturi libere pentru data aleasă. Întoarce-te și alege altă zi.")
        await callback.answer()
        return
    kb = InlineKeyboardBuilder()
    for t in free:
        kb.button(text=t, callback_data=f"slot:{barber_id}:{chosen_date}:{t}")
    kb.adjust(3)
    await callback.message.answer(f"🕒 Alege ora pentru {chosen_date}:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("slot:"))
async def confirm(callback: CallbackQuery):
    _, barber_id, chosen_date, chosen_time = callback.data.split(":")
    barber_id = int(barber_id)

    client = await get_client_by_tgid(callback.from_user.id)
    client_name = client[2] if client else callback.from_user.full_name
    phone = client[3] if client and client[3] else None

    text = (
        f"Confirmezi programarea?\n\n"
        f"• Barber ID: {barber_id}\n"
        f"• Data: {chosen_date}\n"
        f"• Ora: {chosen_time}\n"
        f"• Nume: {client_name}\n"
        f"• Telefon: {phone or '—'}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="Confirmă ✅", callback_data=f"confirm:{barber_id}:{chosen_date}:{chosen_time}")
    kb.button(text="Anulează ❌", callback_data="cancel")
    kb.adjust(2)
    await callback.message.answer(text, reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm:"))
async def finalize(callback: CallbackQuery):
    _, barber_id, chosen_date, chosen_time = callback.data.split(":")
    barber_id = int(barber_id)
    client = await get_client_by_tgid(callback.from_user.id)
    client_name = client[2] if client else callback.from_user.full_name
    phone = client[3] if client and client[3] else None

    # Verificare de ultim moment (race condition)
    free = await get_free_slots(barber_id, chosen_date)
    if chosen_time not in free:
        await callback.message.answer("⚠️ Slotul tocmai a fost ocupat. Te rog alege altă oră.")
        await callback.answer()
        return

    await create_appointment(barber_id, client_name, phone or "", chosen_date, chosen_time)
    await callback.message.answer(f"✅ Programare creată pentru {chosen_date} la {chosen_time}. Mulțumim!")
    await callback.answer()

@dp.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery):
    await callback.message.answer("❌ Programarea a fost anulată. Poți reîncepe cu /start.")
    await callback.answer()

# --- Run ---
async def main():
    await init_db()
    await seed_data()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
