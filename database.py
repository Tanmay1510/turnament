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


class PostgresConnectionWrapper:
    """Wrapper to provide SQLite-like interface for PostgreSQL connections"""
    
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    def execute(self, query, params=()):
        """Execute query and return cursor with SQLite-like interface"""
        # Convert ? to %s for PostgreSQL
        query = query.replace('?', '%s')
        self.cursor.execute(query, params)
        return self.cursor
    
    def executescript(self, script):
        """Execute multiple statements"""
        for statement in script.split(';'):
            if statement.strip():
                self.execute(statement)
        return self.cursor
    
    def commit(self):
        """Commit transaction"""
        self.conn.commit()
    
    def close(self):
        """Close connection"""
        self.cursor.close()
        self.conn.close()
    
    def row_factory(self, value):
        """Dummy to match SQLite interface"""
        pass


def get_connection():
    """Create database connection - PostgreSQL or SQLite"""
    try:
        if USE_POSTGRES:
            conn = psycopg2.connect(DATABASE_URL)
            return PostgresConnectionWrapper(conn)
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
        
        # Create all tables - wrapper handles PostgreSQL conversion
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
            result = conn.execute("SELECT COUNT(*) FROM admin")
            count = result.fetchone()[0]
            if count == 0:
                pw_hash = generate_password_hash('admin123')
                conn.execute(
                    "INSERT INTO admin (username, password_hash) VALUES (?, ?)",
                    ('admin', pw_hash)
                )
                conn.commit()
                print("✓ Default admin created -> username: admin, password: admin123")
        except Exception as e:
            conn.rollback()
            print(f"Admin seeding note: {e}")

        conn.close()
        print("✓ Database tables initialized successfully")
        
    except Exception as e:
        print(f"✗ Database initialization error: {e}")
        raise

if __name__ == '__main__':
    init_db()
    print("Database initialized.")