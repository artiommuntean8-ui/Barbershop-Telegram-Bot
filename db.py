import aiosqlite
from typing import List, Tuple, Optional
from config import DB_PATH, DEFAULT_SLOTS

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS barbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location_id INTEGER NOT NULL,
            FOREIGN KEY(location_id) REFERENCES locations(id))""")
        await db.execute("""CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barber_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            phone TEXT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            FOREIGN KEY(barber_id) REFERENCES barbers(id))""")
        await db.execute("""CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            name TEXT,
            phone TEXT)""")
        await db.commit()

# funcții pentru seed, citire, inserare
async def seed_data():
    async with aiosqlite.connect(DB_PATH) as db:
        for loc in ("Buiucani", "Râșcani", "Centru"):
            await db.execute("INSERT OR IGNORE INTO locations (name) VALUES (?)", (loc,))
        await db.commit()

async def get_locations() -> List[Tuple[int, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM locations ORDER BY name") as cur:
            return await cur.fetchall()

async def get_barbers_by_location(location_id: Optional[int]) -> List[Tuple[int, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        if location_id:
            async with db.execute("SELECT id, name FROM barbers WHERE location_id=?", (location_id,)) as cur:
                return await cur.fetchall()
        else:
            async with db.execute("SELECT id, name FROM barbers") as cur:
                return await cur.fetchall()

async def get_barber_name(barber_id: int) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM barbers WHERE id=?", (barber_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def get_booked_times(barber_id: int, date: str) -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT time FROM appointments WHERE barber_id=? AND date=?", (barber_id, date)) as cur:
            return [r[0] for r in await cur.fetchall()]

async def get_free_slots(barber_id: int, date: str) -> List[str]:
    booked = await get_booked_times(barber_id, date)
    return [t for t in DEFAULT_SLOTS if t not in booked]

async def add_or_update_client(tg_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO clients (tg_id, name) VALUES (?, ?) "
            "ON CONFLICT(tg_id) DO UPDATE SET name=excluded.name",
            (tg_id, name)
        )
        await db.commit()

async def set_client_phone(tg_id: int, phone: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE clients SET phone=? WHERE tg_id=?", (phone, tg_id))
        await db.commit()

async def get_client_by_tgid(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, tg_id, name, phone FROM clients WHERE tg_id=?", (tg_id,)) as cur:
            return await cur.fetchone()

async def create_appointment(barber_id: int, client_name: str, phone: str, date: str, time: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO appointments (barber_id, client_name, phone, date, time) VALUES (?, ?, ?, ?, ?)",
            (barber_id, client_name, phone, date, time)
        )
        await db.commit()

async def get_appointments_for_barber(barber_id: int, date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT client_name, phone, time FROM appointments WHERE barber_id=? AND date=? ORDER BY time",
            (barber_id, date)
        ) as cur:
            return await cur.fetchall()