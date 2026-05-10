import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()
print('.env loaded')

def get_db_path():
    os.makedirs('data', exist_ok=True)
    return r"data/database.db"

def get_db_connection():
    connection = sqlite3.connect(get_db_path())
    connection.row_factory = sqlite3.Row
    return connection
    pass

def init_db():
    connection = get_db_connection()

    schema  = """CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT UNIQUE,
    channel_name TEXT, 
    title TEXT,
    url TEXT,
    published_at TEXT,
    transcript TEXT,
    summary_json TEXT,
    status TEXT DEFAULT 'new',
    processed_at TEXT
    )"""

    connection.execute(schema)
    connection.commit()
    connection.close()
    pass

if __name__ == '__main__':
    init_db()
    print('Database setup complete')