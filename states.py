from aiogram.fsm.state import StatesGroup, State

class Booking(StatesGroup):
    choosing_location = State()
    choosing_barber = State()
    choosing_day = State()
    choosing_time = State()
    confirming = State()

class Phone(StatesGroup):
    waiting_phone = State()
