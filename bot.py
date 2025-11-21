# bot.py
import os
import time
import random
import string
import aiosqlite
import asyncio
from datetime import datetime
from threading import Thread

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

# ---------------- CONFIG ----------------
TOKEN = "8295318379:AAHCycOMdN_xYlrqp_fZRnVmMancsQCBCfk"
ADMINS = [5174856285]
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
    username = (user.username or "")
    first = (user.first_name or "")
    last = (user.last_name or "")
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
        screen_id = cur.lastrowid
    return screen_id

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
        [KeyboardButton(text="💳 Оплатить участие"), KeyboardButton(text="📘 Правила")],
        [KeyboardButton(text="📸 Отправить скрин"), KeyboardButton(text="🎟 Мой билет")]
    ],
    resize_keyboard=True
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📸 Просмотр скринов"), KeyboardButton(text="🎫 Все билеты")],
        [KeyboardButton(text="🎟 Выдать билет"), KeyboardButton(text="🗑 Удалить билет")],
        [KeyboardButton(text="🚪 Выйти из панели")]
    ],
    resize_keyboard=True
)

# ---------------- Bot commands ----------------
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
            "Привет! Чтобы принять участие:\n1) Оплати участие — 💳\n2) Отправь скрин — 📸\n3) После проверки админ выдаст билет",
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

# ---------------- Photo / Screen handler ----------------
@dp.message(lambda m: m.photo is not None)
async def photo_handler(message: Message):
    await add_or_update_user(message.from_user)
    file_id = message.photo[-1].file_id

    try:
        file_info = await bot.get_file(file_id)
    except Exception as e:
        await message.answer("❌ Ошибка при получении файла.")
        print("get_file error:", e)
        return

    file_ext = ".jpg"
    file_path = os.path.join(SCREENS_DIR, f"{file_id}{file_ext}")

    try:
        await file_info.download(destination=file_path)
    except Exception as e:
        await message.answer("❌ Не удалось сохранить файл.")
        print("download error:", e)
        return

    username = (message.from_user.username or "").lstrip("@")
    screen_id = await add_screen(message.from_user.id, username, file_path)
    await message.answer(f"✅ Скрин сохранён. Отправьте его админу: @Belldari")

# ---------------- Admin buttons ----------------
@dp.message()
async def handle_buttons(message: Message):
    text = (message.text or "").strip()
    await add_or_update_user(message.from_user)

    if message.from_user.id in ADMINS:
        if text == "🚪 Выйти из панели":
            await message.answer("Вы вышли из панели администратора.", reply_markup=user_keyboard)
            return
        # другие админ кнопки пока выводят инструкцию
        if text == "🎟 Выдать билет":
            return await message.answer("Используйте команду:\n/give user_id")
        if text == "🗑 Удалить билет":
            return await message.answer("Используйте команду:\n/del_ticket user_id [ticket_code]")
        if text == "📸 Просмотр скринов":
            return await message.answer("Скрины приходят через кнопку 'Отправьте скрин админу @Belldari'")
        if text == "🎫 Все билеты":
            return await message.answer("Список билетов через команду /all_tickets")

    # User buttons
    if text == "💳 Оплатить участие":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=PAY_LINK)]
        ])
        return await message.answer("Нажми кнопку для оплаты:", reply_markup=kb)
    if text == "📘 Правила":
        return await cmd_rule(message)
    if text == "🎟 Мой билет":
        ticket = await ticket_for_user(message.from_user.id)
        if ticket:
            return await message.answer(f"🎟 Ваш билет: `{ticket}`", parse_mode="Markdown")
        return await message.answer("❌ У вас пока нет билета. После проверки админ выдаст билет.")
    if text == "📸 Отправить скрин":
        return await message.answer("Отправьте скрин админу: @Belldari")

# ---------------- Admin commands ----------------
@dp.message(Command("give"))
async def cmd_give(message: Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("❌ Нет доступа.")
    parts = (message.text or "").split()
    if len(parts) < 2:
        return await message.answer("Использование: /give user_id")
    try:
        target_id = int(parts[1])
    except:
        return await message.answer("user_id должен быть числом")
    existing = await ticket_for_user(target_id)
    if existing:
        return await message.answer(f"❌ У пользователя уже есть билет: `{existing}`", parse_mode="Markdown")
    ticket_code = generate_ticket_code()
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT username FROM users WHERE user_id = ? LIMIT 1;", (target_id,))
        row = await cur.fetchone()
        await cur.close()
    username = row[0] if row and row[0] else ""
    await add_ticket(target_id, username, ticket_code)
    await message.answer(f"🎟 Билет `{ticket_code}` выдан пользователю {target_id}", parse_mode="Markdown")
    try:
        await bot.send_message(target_id, f"🎟 Вам выдан билет: `{ticket_code}`", parse_mode="Markdown")
    except:
        pass

@dp.message(Command("del_ticket"))
async def cmd_del_ticket(message: Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("❌ Нет доступа.")
    parts = (message.text or "").split()
    if len(parts) < 2:
        return await message.answer("Использование: /del_ticket user_id [ticket_code]")
    try:
        target_id = int(parts[1])
    except:
        return await message.answer("user_id должен быть числом")
    ticket_code = parts[2] if len(parts) >= 3 else None
    await delete_ticket(target_id, ticket_code)
    await message.answer("✅ Билет(ы) удалены.")
    try:
        if ticket_code:
            await bot.send_message(target_id, f"❌ Ваш билет `{ticket_code}` был удалён администратором.")
        else:
            await bot.send_message(target_id, "❌ Ваш(и) билет(ы) были удалены администратором.")
    except:
        pass

# ---------------- Keep alive server ----------------
def run_flask():
    from flask import Flask
    app = Flask("keep_alive")

    @app.route("/")
    def main():
        return "Bot is running!"

    @app.route("/ping")
    def ping():
        return "pong"

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ---------------- STARTUP ----------------
async def main():
    await init_db()
    await set_bot_commands()
    keep_alive()
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())