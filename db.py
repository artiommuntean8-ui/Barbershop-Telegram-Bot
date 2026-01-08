import aiosqlite
from typing import List, Tuple
from config import DB_PATH, DEFAULT_SLOTS

# --- Schema ---
CREATE_LOCATIONS = """
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
"""

CREATE_BARBERS = """
CREATE TABLE IF NOT EXISTS barbers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location_id INTEGER NOT NULL,
    FOREIGN KEY(location_id) REFERENCES locations(id)
);
"""

CREATE_APPOINTMENTS = """
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barber_id INTEGER NOT NULL,
    client_id INTEGER,
    client_name TEXT NOT NULL,
    phone TEXT,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(barber_id) REFERENCES barbers(id)
);
"""

CREATE_CLIENTS = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE,
    name TEXT,
    phone TEXT
);
"""

# --- Init & seed ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_LOCATIONS)
        await db.execute(CREATE_BARBERS)
        await db.execute(CREATE_APPOINTMENTS)
        await db.execute(CREATE_CLIENTS)
        await db.commit()

async def seed_data():
    async with aiosqlite.connect(DB_PATH) as db:
        # Locații
        locations = ["Buiucani", "Râșcani", "Centru"]
        for loc in locations:
            await db.execute("INSERT OR IGNORE INTO locations (name) VALUES (?)", (loc,))
        # Barberi per locație (exemplu)
        # Obține id-urile locațiilor
        loc_ids = {}
        async with db.execute("SELECT id, name FROM locations") as cur:
            for row in await cur.fetchall():
                loc_ids[row[1]] = row[0]

        barbers_seed = [
            ("Mihai", loc_ids["Buiucani"]),
            ("Sergiu", loc_ids["Buiucani"]),
            ("Andrei", loc_ids["Râșcani"]),
            ("Vlad", loc_ids["Centru"]),
            ("Ion", loc_ids["Centru"]),
        ]
        for name, location_id in barbers_seed:
            await db.execute(
                "INSERT INTO barbers (name, location_id) SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM barbers WHERE name=? AND location_id=?)",
                (name, location_id, name, location_id)
            )
        await db.commit()

# --- Helpers ---
async def get_locations() -> List[Tuple[int, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM locations ORDER BY name") as cur:
            return await cur.fetchall()

async def get_barbers_by_location(location_id: int) -> List[Tuple[int, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM barbers WHERE location_id=? ORDER BY name", (location_id,)) as cur:
            return await cur.fetchall()

async def get_booked_times(barber_id: int, date: str) -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT time FROM appointments WHERE barber_id=? AND date=?", (barber_id, date)) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

async def get_free_slots(barber_id: int, date: str) -> List[str]:
    booked = await get_booked_times(barber_id, date)
    return [t for t in DEFAULT_SLOTS if t not in booked]

async def add_or_update_client(tg_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO clients (tg_id, name) VALUES (?, ?) ON CONFLICT(tg_id) DO UPDATE SET name=excluded.name",
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
