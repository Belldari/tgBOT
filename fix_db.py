import sqlite3

db = sqlite3.connect("database.db")
cur = db.cursor()

try:
    cur.execute("ALTER TABLE tickets ADD COLUMN ticket TEXT;")
    print("Колонка 'ticket' успешно добавлена.")
except Exception as e:
    print("Ошибка или колонка уже существует:", e)

db.commit()
db.close()

print("Готово!")