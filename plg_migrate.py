"""
PLG Phase 1 - Database migration
Adds users, subscriptions, usage_log, referrals; adds user_id/share_hash where needed.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'braingym.db')

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tier TEXT DEFAULT 'free',
            generations_this_month INTEGER DEFAULT 0,
            generations_limit INTEGER DEFAULT 10,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (referred_by) REFERENCES users(id)
        )
    ''')

    # 2. Subscriptions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tier TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            current_period_start TIMESTAMP,
            current_period_end TIMESTAMP,
            cancel_at_period_end BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 3. Usage log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 4. Referrals
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referee_id INTEGER NOT NULL,
            signup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            converted BOOLEAN DEFAULT 0,
            reward_granted BOOLEAN DEFAULT 0,
            FOREIGN KEY (referrer_id) REFERENCES users(id),
            FOREIGN KEY (referee_id) REFERENCES users(id)
        )
    ''')

    # 5. Add user_id to voice_profile if missing
    if not column_exists(cursor, 'voice_profile', 'user_id'):
        try:
            cursor.execute('ALTER TABLE voice_profile ADD COLUMN user_id INTEGER')
        except sqlite3.OperationalError:
            pass

    # 6. Add user_id and share_hash to generations if missing
    if not column_exists(cursor, 'generations', 'user_id'):
        try:
            cursor.execute('ALTER TABLE generations ADD COLUMN user_id INTEGER')
        except sqlite3.OperationalError:
            pass
    if not column_exists(cursor, 'generations', 'share_hash'):
        try:
            cursor.execute('ALTER TABLE generations ADD COLUMN share_hash TEXT')
        except sqlite3.OperationalError:
            pass

    # 7. Conversion engine: trial_key on insights, onboarding/testimonial on users
    if not column_exists(cursor, 'insights', 'trial_key'):
        try:
            cursor.execute('ALTER TABLE insights ADD COLUMN trial_key TEXT')
        except sqlite3.OperationalError:
            pass
    if not column_exists(cursor, 'insights', 'user_id'):
        try:
            cursor.execute('ALTER TABLE insights ADD COLUMN user_id INTEGER')
        except sqlite3.OperationalError:
            pass
    if not column_exists(cursor, 'users', 'onboarding_completed'):
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN onboarding_completed INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
    if not column_exists(cursor, 'users', 'testimonial_requested'):
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN testimonial_requested INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass

    # 8. Testimonials table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS testimonials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            rating INTEGER,
            allow_public INTEGER DEFAULT 0,
            twitter_handle TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            featured INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✓ PLG database migration complete")

if __name__ == '__main__':
    run_migration()
