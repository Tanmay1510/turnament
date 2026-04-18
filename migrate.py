import sqlite3

c = sqlite3.connect('tournament.db', timeout=10)

try:
    c.execute('ALTER TABLE matches ADD COLUMN game_data TEXT')
    c.commit()
    print("Column added successfully")
except Exception as e:
    print(f"Note: {e}")

cols = [r[1] for r in c.execute('PRAGMA table_info(matches)').fetchall()]
print("Columns:", cols)

c.close()