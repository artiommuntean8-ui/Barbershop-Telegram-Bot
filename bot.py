import asyncio
import logging
from datetime import date, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from states import Booking, Phone
from db import (
    init_db, seed_data, get_locations, get_barbers_by_location,
    get_free_slots, get_client_by_tgid, add_or_update_client,
    set_client_phone, create_appointment, get_barber_name
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

@dp.message(Phone.waiting_phone)
async def invalid_phone(message: Message):
    await message.answer("Format invalid. Exemplu: +37360123456")

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
    barber_id = int(callback.data.split(":")[1])
    await state.update_data(barber_id=barber_id)

    kb = InlineKeyboardBuilder()
    for dval, dlabel in day_options():
        kb.button(text=dlabel, callback_data=f"day:{dval}")
    kb.adjust(3)
    await state.set_state(Booking.choosing_day)
    await callback.message.answer("🗓 Alege ziua:", reply_markup=kb.as_markup())

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
async def finalize(callback: CallbackQuery, state: FSMContext