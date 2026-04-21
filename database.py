import sqlite3
import os
from werkzeug.security import generate_password_hash

# Use /tmp for production (Render), current dir for development
if os.environ.get('RENDER'):
    DB_PATH = '/tmp/tournament.db'
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tournament.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    try:
        conn = get_connection()

        # Create tables one by one with better error handling
        conn.execute("""
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sport TEXT NOT NULL,
            status TEXT DEFAULT 'upcoming',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            short_name TEXT,
            color TEXT DEFAULT '#3B82F6',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            number INTEGER,
            role TEXT DEFAULT 'player',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            team1_id INTEGER NOT NULL,
            team2_id INTEGER NOT NULL,
            match_type TEXT DEFAULT 'group',
            status TEXT DEFAULT 'upcoming',
            score1 TEXT DEFAULT '0',
            score2 TEXT DEFAULT '0',
            winner_id INTEGER,
            game_data TEXT DEFAULT '{}',
            scheduled_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
            FOREIGN KEY (team1_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (team2_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (winner_id) REFERENCES teams(id)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()

        # Seed default admin
        try:
            count = conn.execute("SELECT COUNT(*) FROM admin").fetchone()[0]
            if count == 0:
                pw_hash = generate_password_hash('admin123')
                conn.execute(
                    "INSERT INTO admin (username, password_hash) VALUES (?, ?)",
                    ('admin', pw_hash)
                )
                conn.commit()
                print("Default admin created -> username: admin, password: admin123")
        except sqlite3.IntegrityError:
            conn.rollback()
            pass

        conn.close()
        print(f"✓ Database initialized at {DB_PATH}")
        
    except Exception as e:
        print(f"✗ Database initialization error: {e}")
        raise


if __name__ == '__main__':
    init_db()
    print("Database initialized.")