import os
import time
import random
import string
import aiosqlite
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
)
from aiogram.filters import Command

# ---------------- Load .env ----------------
load_dotenv()
TOKEN = os.getenv("8295318379:AAGykLEFNGOzK7Yzdn4JQnFFo9EtvXU4pUU")
ADMINS = [int(x) for x in os.getenv("5174856285", "").split(",")]
PAY_LINK = os.getenv("https://yoomoney.ru/fundraise/1E44DJ5RI06.251118", "")
DB_FILE = "database.db"
SCREENS_DIR = "screens"

# ---------------- Init ----------------
bot = Bot(token=TOKEN)
dp = Dispatcher()

os.makedirs(SCREENS_DIR, exist_ok=True)

# ---------------- Database ----------------
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at INTEGER
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS screens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            file_path TEXT,
            status TEXT DEFAULT 'new',
            created_at INTEGER
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            ticket TEXT,
            created_at INTEGER
        );
        """)
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

async def add_screen(user_id, username, file_path):
    now = int(time.time())
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute(
            "INSERT INTO screens (user_id, username, file_path, created_at) VALUES (?, ?, ?, ?);",
            (user_id, username or "", file_path, now)
        )
        await db.commit()
        return cur.lastrowid

async def get_new_screens():
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute(
            "SELECT id, user_id, username, file_path, created_at, status FROM screens WHERE status IN ('new','sent') ORDER BY id ASC;"
        )
        rows = await cur.fetchall()
        await cur.close()
        return rows

async def set_screen_status(screen_id, status):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE screens SET status = ? WHERE id = ?;", (status, screen_id))
        await db.commit()

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
            await db.execute("DELETE FROM tickets WHERE user_id = ? AND ticket = ?;", (user_id, ticket_code))
        else:
            await db.execute("DELETE FROM tickets WHERE user_id = ?;", (user_id,))
        await db.commit()

async def ticket_for_user(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT ticket FROM tickets WHERE user_id = ? ORDER BY id DESC LIMIT 1;", (user_id,))
        row = await cur.fetchone()
        await cur.close()
    return row[0] if row else None

async def get_all_tickets_rows():
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT username, ticket, created_at FROM tickets ORDER BY created_at DESC;")
        rows = await cur.fetchall()
        await cur.close()
        return rows

def generate_ticket_code():
    digits = ''.join(random.choices("0123456789", k=4))
    letters = ''.join(random.choices(string.ascii_uppercase, k=5))
    return f"{digits}-{letters}"

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

# ---------------- Commands ----------------
async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="♻ Перезапуск"),
        BotCommand(command="rule", description="📘 Правила"),
        BotCommand(command="support", description="👨💻 Поддержка"),
        BotCommand(command="admin", description="👨💻 Админ-панель")
    ]
    await bot.set_my_commands(commands)

# ---------------- Handlers ----------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await add_or_update_user(message.from_user)
    if message.from_user.id in ADMINS:
        await message.answer("Панель администратора:", reply_markup=admin_keyboard)
    else:
        await message.answer(
            f"Привет! Чтобы принять участие:\n1) Оплати участие — 💳\n2) Отправь скрин — 📸\n3) После проверки админ выдаст билет\n\n"
            f"Если хотите отправить скрин напрямую админу: @Belldari",
            reply_markup=user_keyboard
        )

@dp.message(Command("rule"))
async def cmd_rule(message: Message):
    text = (
        "📜 *Регламент турнира:*\n\n"
        "1️⃣ Организация не отвечает за ваше интернет-соединение и ошибки в работе игры.\n"
        "2️⃣ Возврат денег за участие невозможен.\n"
        "3️⃣ Неявка на турнир — техническое поражение (ожидание 15 минут).\n"
        "4️⃣ Читы — техническое поражение.\n"
        "5️⃣ Подставной матч — техническое поражение.\n"
        "6️⃣ Каждый игрок может участвовать в турнире только с одного игрового аккаунта.\n"
        "7️⃣ Игры проходят в формате bo3 (best of 3), в игровом режиме \"1на1\"."
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("support"))
async def cmd_support(message: Message):
    await message.answer("👨💻 Служба поддержки: @Belldari")

# ---------------- Run ----------------
async def main():
    await init_db()
    await set_bot_commands()
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())