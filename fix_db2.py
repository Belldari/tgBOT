import sqlite3

db = sqlite3.connect("database.db")
cur = db.cursor()

# Проверяем, есть ли колонка id
try:
    cur.execute("SELECT id FROM tickets LIMIT 1;")
    print("Колонка id уже существует.")
except:
    print("Добавляем колонку id...")
    cur.execute("ALTER TABLE tickets ADD COLUMN id INTEGER;")

# Проверяем ticket
try:
    cur.execute("SELECT ticket FROM tickets LIMIT 1;")
    print("Колонка ticket уже существует.")
except:
    print("Добавляем колонку ticket...")
    cur.execute("ALTER TABLE tickets ADD COLUMN ticket TEXT;")

# Делаем id уникальным автоинкрементным
print("Обновляем структуру таблицы...")

cur.execute("""
CREATE TABLE IF NOT EXISTS tickets_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ticket TEXT,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# Переносим старые данные
cur.execute("""
INSERT INTO tickets_new (user_id, ticket)
SELECT user_id, ticket FROM tickets;
""")

# Меняем таблицы местами
cur.execute("DROP TABLE tickets;")
cur.execute("ALTER TABLE tickets_new RENAME TO tickets;")

db.commit()
db.close()

print("Готово! Таблица исправлена.")