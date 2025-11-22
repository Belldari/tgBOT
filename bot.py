import os
import time
import random
import string
import aiosqlite
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
)
from aiogram.filters import Command
import aiohttp
import signal
import sys

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN")  # Токен бота из Render
PAY_LINK = os.getenv("PAY_LINK")  # Ссылка на оплату
ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",")]  # Список ID админов
DB_FILE = "database.db"
PING_URL = os.getenv("PING_URL")  # Для Render ping

# ---------------- INIT ----------------
bot = Bot(token=TOKEN)
dp = Dispatcher()

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
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            ticket TEXT,
            created_at INTEGER
        );""")
        await db.commit()

async def add_or_update_user(user):
    if not user: return
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

async def add_ticket(user_id, username, ticket_code):
    now = int(time.time())
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO tickets (user_id, username, ticket, created_at) VALUES (?, ?, ?, ?);",
            (user_id, username or "", ticket_code, now)
        )
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
        [KeyboardButton(text="💳 Оплатить участие"), KeyboardButton(text="📘 Правила")],
        [KeyboardButton(text="🎟 Мой билет"), KeyboardButton(text="📸 Отправить скрин")]
    ], resize_keyboard=True
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎫 Все билеты"), KeyboardButton(text="🎟 Выдать билет")],
        [KeyboardButton(text="🗑 Удалить билет"), KeyboardButton(text="🚪 Выйти из панели")]
    ], resize_keyboard=True
)

# ---------------- Set commands ----------------
async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="♻ Перезапуск"),
        BotCommand(command="rule", description="📘 Правила"),
        BotCommand(command="support", description="👨💻 Поддержка"),
        BotCommand(command="admin", description="👨💻 Админ-панель")
    ]
    await bot.set_my_commands(commands)

# ---------------- Admin + User Handlers ----------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await add_or_update_user(message.from_user)
    if message.from_user.id in ADMINS:
        await message.answer("Панель администратора:", reply_markup=admin_keyboard)
    else:
        await message.answer(
            "Привет! Чтобы принять участие:\n"
            "1) Оплати участие — 💳\n"
            "2) Отправь скрин админу — 📸 @Belldari\n"
            "3) После подтверждения админ выдаст билет",
            reply_markup=user_keyboard
        )

@dp.message(Command("rule"))
async def cmd_rule(message: Message):
    await message.answer(
        "📜 *Регламент турнира:*\n"
        "1️⃣ Организация не отвечает за интернет.\n"
        "2️⃣ Возврат денег невозможен.\n"
        "3️⃣ Неявка = техническое поражение.\n"
        "4️⃣ Читы = техническое поражение.\n"
        "5️⃣ Подставной матч = техническое поражение.\n"
        "6️⃣ Один аккаунт на игрока.\n"
        "7️⃣ Формат bo3, режим 1на1.",
        parse_mode="Markdown"
    )

@dp.message(Command("support"))
async def cmd_support(message: Message):
    await message.answer("👨💻 Служба поддержки: @Belldari")

@dp.message()
async def handle_buttons(message: Message):
    text = (message.text or "").strip()
    await add_or_update_user(message.from_user)

    # ---------------- ADMIN PANEL ----------------
    if message.from_user.id in ADMINS:
        if text == "🎫 Все билеты":
            rows = await get_all_tickets_rows()
            if not rows: return await message.answer("🎟 Билетов нет.")
            out = "🎫 *Выданные билеты:*\n\n"
            for username, ticket, created_at in rows:
                dt = datetime.fromtimestamp(created_at).strftime("%d.%m.%Y %H:%M")
                uname = f"@{username}" if username else "user_id неизвестен"
                out += f"👤 {uname}\n🎟 {ticket}\n🕒 {dt}\n\n"
            return await message.answer(out, parse_mode="Markdown")
        if text == "🎟 Выдать билет":
            return await message.answer("Используйте команду:\n/give user_id")
        if text == "🗑 Удалить билет":
            return await message.answer("Используйте команду:\n/del_ticket user_id [ticket_code]")
        if text == "🚪 Выйти из панели":
            await message.answer("Вы вышли из панели администратора.", reply_markup=user_keyboard)
            return

    # ---------------- USER BUTTONS ----------------
    if text == "💳 Оплатить участие":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить", url=PAY_LINK)]])
        return await message.answer("Нажми кнопку для оплаты:", reply_markup=kb)
    if text == "📘 Правила": return await cmd_rule(message)
    if text == "🎟 Мой билет":
        ticket = await ticket_for_user(message.from_user.id)
        if ticket: return await message.answer(f"🎟 Ваш билет: `{ticket}`", parse_mode="Markdown")
        return await message.answer("❌ Билета пока нет.")
    if text == "📸 Отправить скрин":
        return await message.answer("Отправьте скрин админу: @Belldari и ждите подтверждения")

# ---------------- STARTUP ----------------
async def main():
    await init_db()
    await set_bot_commands()

    # keep_alive для Render
    async def keep_alive():
        if not PING_URL: return
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(PING_URL) as resp:
                        print(f"Ping {PING_URL}: {resp.status}")
                except:
                    pass
                await asyncio.sleep(25*60)

    asyncio.create_task(keep_alive())

    # ---------------- Fake port для Render ----------------
    PORT = int(os.getenv("PORT", 8080))
    server = await asyncio.start_server(lambda r, w: None, "0.0.0.0", PORT)
    print(f"Fake port bound on {PORT}")

    # ---------------- Start bot polling ----------------
    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        print("Polling stopped")
    except Exception as e:
        print("BOT ERROR:", e)
    finally:
        await bot.session.close()
        server.close()
        await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
        sys.exit()
