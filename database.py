import sqlite3
import os
from werkzeug.security import generate_password_hash

# Check for PostgreSQL connection (Vercel/production)
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    print("✓ Using PostgreSQL database")
else:
    # SQLite for local development
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tournament.db')
    print(f"✓ Using SQLite database at {DB_PATH}")


def get_connection():
    """Create database connection - PostgreSQL or SQLite"""
    try:
        if USE_POSTGRES:
            conn = psycopg2.connect(DATABASE_URL)
            # Make cursor return dicts like sqlite3.Row
            return conn
        else:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys = ON')
            return conn
    except Exception as e:
        print(f"✗ Database connection error: {e}")
        raise


def init_db():
    """Initialize database tables"""
    try:
        conn = get_connection()
        
        if USE_POSTGRES:
            # PostgreSQL schema
            cursor = conn.cursor()
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tournaments (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                sport TEXT NOT NULL,
                status TEXT DEFAULT 'upcoming',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id SERIAL PRIMARY KEY,
                tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                short_name TEXT,
                color TEXT DEFAULT '#3B82F6',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id SERIAL PRIMARY KEY,
                team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                number INTEGER,
                role TEXT DEFAULT 'player',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id SERIAL PRIMARY KEY,
                tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
                team1_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                team2_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                match_type TEXT DEFAULT 'group',
                status TEXT DEFAULT 'upcoming',
                score1 TEXT DEFAULT '0',
                score2 TEXT DEFAULT '0',
                winner_id INTEGER REFERENCES teams(id),
                game_data TEXT DEFAULT '{}',
                scheduled_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            conn.commit()
            
            # Seed default admin
            try:
                cursor.execute("SELECT COUNT(*) FROM admin")
                count = cursor.fetchone()[0]
                if count == 0:
                    pw_hash = generate_password_hash('admin123')
                    cursor.execute(
                        "INSERT INTO admin (username, password_hash) VALUES (%s, %s)",
                        ('admin', pw_hash)
                    )
                    conn.commit()
                    print("✓ Default admin created -> username: admin, password: admin123")
            except Exception as e:
                conn.rollback()
                print(f"Admin seeding note: {e}")
            
            cursor.close()
            
        else:
            # SQLite schema
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
                    print("✓ Default admin created -> username: admin, password: admin123")
            except sqlite3.IntegrityError:
                conn.rollback()
                pass

        conn.close()
        print("✓ Database tables initialized successfully")
        
    except Exception as e:
        print(f"✗ Database initialization error: {e}")
        raise


class Database:
    """Wrapper class to handle both SQLite and PostgreSQL with consistent interface"""
    
    @staticmethod
    def convert_query(query):
        """Convert SQLite ? placeholders to PostgreSQL %s if needed"""
        if USE_POSTGRES:
            # Replace ? with %s for PostgreSQL
            return query.replace('?', '%s')
        return query
    
    @staticmethod
    def execute(conn, query, params=()):
        """Execute query with automatic parameter conversion"""
        query = Database.convert_query(query)
        if USE_POSTGRES:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor
        else:
            return conn.execute(query, params)
    
    @staticmethod
    def dict_from_row(row):
        """Convert database row to dict - handles both SQLite and PostgreSQL"""
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        return dict(row)


if __name__ == '__main__':
    init_db()
    print("Database initialized.")