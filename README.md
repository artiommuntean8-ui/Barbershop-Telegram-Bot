# Barbershop Telegram Bot

A comprehensive Telegram bot for managing barbershop appointments, built with Python using `aiogram` and `aiosqlite`.

## Features

- **Booking System**: Users can book appointments by choosing a location, a specific barber, a date, and an available time slot.
- **Barber Profiles**: View barber experience and specialties during the booking process.
- **Client Management**: Automated client registration and phone number updates.
- **Reminders**: Automated reminders sent 1 hour before the scheduled appointment.
- **Admin Panel**:
    - View daily schedules for each barber.
    - Broadcast messages to all registered clients.
    - Upload photos to a public gallery.
- **Promo Codes**: Support for discount codes (e.g., PROMO20, FIRST10).
- **Price List**: Easily accessible service menu and pricing.
- **Personal Agenda**: Users can view and cancel their upcoming bookings.

## Tech Stack

- **Language**: Python 3.8+
- **Framework**: aiogram 3.x (Asynchronous Telegram Bot API)
- **Database**: aiosqlite (Asynchronous SQLite wrapper)
- **Environment**: python-dotenv

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Barbershop-Bot
   ```

2. **Install dependencies**:
   ```bash
   pip install aiogram aiosqlite python-dotenv
   ```

3. **Configuration**:
   Create a `.env` file in the root directory with the following variables:
   ```env
   BOT_TOKEN=your_telegram_bot_token_here
   DB_PATH=barbershop.db
   ```
   *Note: Update the `ADMINS` list in `bot.py` with your Telegram User ID to access admin features.*

4. **Initialize Database**:
   The bot automatically initializes the database and seeds initial data (locations) on the first run via `init_db()` and `seed_data()`.

5. **Run the bot**:
   ```bash
   python bot.py
   ```

## Bot Commands

### User Commands
- `/start` - Main menu and booking start.
- `/help` - List available commands.
- `/prices` - Show services and prices.
- `/mybookings` - View current appointments.
- `/cancel` - Cancel an existing appointment.
- `/promo [CODE]` - Apply a discount code.
- `/gallery` - View work examples.

### Admin Commands
- `/admin` - Access the administration panel (requires ID in `ADMINS` list).
- `/broadcast [message]` - Send a notification to all users.
- `/addphoto` - Upload a photo to the gallery (send with a photo).

## Project Structure

- `bot.py`: Main entry point and message handlers.
- `db.py`: Database schema and async CRUD operations.
- `config.py`: Configuration settings, promo codes, and service prices.
- `states.py`: FSM (Finite State Machine) definitions for booking and input flows.

## License
MIT