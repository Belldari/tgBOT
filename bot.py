import os
import time
import random
import string
import aiosqlite
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand
)
from aiogram.filters import Command
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------
load_dotenv()

TOKEN = os.getenv("8295318379:AAGykLEFNGOzK7Yzdn4JQnFFo9EtvXU4pUU")
ADMINS = [int(x) for x in os.getenv("5174856285", "").split(",") if x]

PAY_LINK = "https://yoomoney.ru/fundraise/1E44DJ5RI06.251118"
DB_FILE = "database.db"
SCREENS_DIR = "screens"

# ---------------- INIT ----------------
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- Ensure folders ----------------
os.makedirs(SCREENS_DIR, exist_ok=True)

# ---------------- Database helpers ----------------
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at INTEGER
        );""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS screens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            file_path TEXT,
            status TEXT DEFAULT 'new',
            created_at INTEGER
        );""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            ticket TEXT,
            created_at INTEGER
        );""")
        await db.commit()

async def add_or_update_user(user):
    if not user:
        return
    uid = user.id
    username = user.username or ""
    first = user.first_name or ""
    last = user.last_name or ""
    now = int(time.time())
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_name=excluded.last_name;
        """, (uid, username, first, last, now))
        await db.commit()

# ---------------- Ticket helpers ----------------
def generate_ticket_code():
    digits = ''.join(random.choices("0123456789", k=4))
    letters = ''.join(random.choices(string.ascii_uppercase, k=5))
    return f"{digits}-{letters}"

async def ticket_for_user(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT ticket FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 1;", (user_id,))
        row = await cur.fetchone()
        await cur.close()
    return row[0] if row else None

async def add_ticket(user_id, username, ticket_code):
    now = int(time.time())
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO tickets (user_id, username, ticket, created_at) VALUES (?, ?, ?, ?);",
            (user_id, username or "", ticket_code, now)
        )
        await db.commit()

async def delete_ticket(user_id, ticket_code=None):
    async with aiosqlite.connect(DB_FILE) as db:
        if ticket_code:
            await db.execute("DELETE FROM tickets WHERE user_id=? AND ticket=?;", (user_id, ticket_code))
        else:
            await db.execute("DELETE FROM tickets WHERE user_id=?;", (user_id,))
        await db.commit()

# ---------------- Screens helpers ----------------
async def add_screen(user_id, username, file_path):
    now = int(time.time())
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute(
            "INSERT INTO screens (user_id, username, file_path, created_at) VALUES (?, ?, ?, ?);",
            (user_id, username or "", file_path, now)
        )
        await db.commit()
        return cur.lastrowid

# ---------------- Keyboards ----------------
user_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("💳 Оплатить участие"), KeyboardButton("📘 Правила")],
        [KeyboardButton("📸 Отправить скрин"), KeyboardButton("🎟 Мой билет")]
    ],
    resize_keyboard=True
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("📸 Просмотр скринов"), KeyboardButton("🎫 Все билеты")],
        [KeyboardButton("🎟 Выдать билет"), KeyboardButton("🗑 Удалить билет")],
        [KeyboardButton("🚪 Выйти из панели")]
    ],
    resize_keyboard=True
)

# ---------------- Bot commands ----------------
async def set_bot_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="♻ Перезапуск"),
        BotCommand(command="rule", description="📘 Правила"),
        BotCommand(command="support", description="👨💻 Поддержка"),
        BotCommand(command="admin", description="👨💻 Админ-панель")
    ])

# ---------------- Handlers ----------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await add_or_update_user(message.from_user)
    if message.from_user.id in ADMINS:
        await message.answer("Панель администратора:", reply_markup=admin_keyboard)
    else:
        await message.answer(
            "Привет! Чтобы принять участие:\n1) Оплати участие — 💳\n2) Отправь скрин — 📸\n3) После проверки админ выдаст билет",
            reply_markup=user_keyboard
        )

@dp.message(Command("rule"))
async def cmd_rule(message: Message):
    await message.answer(
        "📜 *Регламент турнира:*\n\n1️⃣ Организация не отвечает за ваше интернет-соединение.\n2️⃣ Возврат денег невозможен.\n3️⃣ Неявка — техническое поражение.\n4️⃣ Читы — дисквалификация.\n5️⃣ Только один аккаунт на игрока.\n6️⃣ Формат bo3.",
        parse_mode="Markdown"
    )

@dp.message(Command("support"))
async def cmd_support(message: Message):
    await message.answer("👨💻 Поддержка: @Belldari")

# ---------------- Send screenshots to admin ----------------
@dp.message(lambda m: m.photo is not None)
async def photo_handler(message: Message):
    await add_or_update_user(message.from_user)
    file_id = message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    file_path = os.path.join(SCREENS_DIR, f"{file_id}.jpg")
    await file_info.download(destination=file_path)
    screen_id = await add_screen(message.from_user.id, message.from_user.username or "", file_path)
    await message.answer(f"✅ Скрин сохранён. Отправьте его админу: @Belldari")

# ---------------- Main ----------------
async def main():
    await init_db()
    await set_bot_commands()
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
