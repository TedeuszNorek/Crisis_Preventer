import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "users.db")

def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Tworzy tabele jeśli nie istnieją."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                referred_by INTEGER,
                is_pro BOOLEAN DEFAULT 0,
                pro_expires_at INTEGER DEFAULT 0,
                lifetime BOOLEAN DEFAULT 0,
                created_at INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crypto_invoices (
                invoice_id INTEGER PRIMARY KEY,
                telegram_id INTEGER,
                tier TEXT,
                status TEXT DEFAULT 'active',
                created_at INTEGER
            )
        ''')
        conn.commit()

def upsert_user(telegram_id: int, referred_by: int = None):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (telegram_id, referred_by, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                referred_by = COALESCE(users.referred_by, excluded.referred_by)
        ''', (telegram_id, referred_by, int(time.time())))
        conn.commit()
    
    # Po dodaniu użytkownika, sprawdź czy polecający (referrer) nie zasłużył na PRO (3 polecenia)
    if referred_by:
        check_and_award_referral_pro(referred_by)

def check_and_award_referral_pro(referrer_id: int):
    """Sprawdza czy użytkownik ma 3 polecenia i nadaje PRO."""
    count = get_referral_count(referrer_id)
    if count >= 3:
        grant_pro_access(referrer_id, lifetime=True)

def get_referral_count(telegram_id: int) -> int:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE referred_by = ?', (telegram_id,))
        row = cursor.fetchone()
        return row['count'] if row else 0

def get_user_status(telegram_id: int):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT is_pro, lifetime, pro_expires_at FROM users WHERE telegram_id = ?', (telegram_id,))
        row = cursor.fetchone()
        if not row:
            upsert_user(telegram_id)
            return {"is_pro": False, "referral_count": 0}
        
        return {
            "is_pro": is_user_pro(telegram_id),
            "referral_count": get_referral_count(telegram_id)
        }

def is_user_pro(telegram_id: int) -> bool:
    """Zdejmujemy PRO - teraz każdy jest Pro (Zgodnie z prośbą użytkownika)."""
    return True

def grant_pro_access(telegram_id: int, duration_days: int = None, lifetime: bool = False):
    with _get_connection() as conn:
        cursor = conn.cursor()
        upsert_user(telegram_id)
        
        if lifetime:
            cursor.execute('''
                UPDATE users SET is_pro = 1, lifetime = 1 WHERE telegram_id = ?
            ''', (telegram_id,))
        else:
            expires_at = int(time.time()) + (duration_days * 86400)
            cursor.execute('''
                UPDATE users SET is_pro = 1, pro_expires_at = ? WHERE telegram_id = ?
            ''', (expires_at, telegram_id))
        conn.commit()

def process_paid_invoice(invoice_id: int, telegram_id: int):
    """Zapisuje fakturę jako opłaconą chroniąc przed podwójnym dodaniem tej samej."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO crypto_invoices (invoice_id, telegram_id, tier, created_at)
                VALUES (?, ?, ?, ?)
            ''', (invoice_id, telegram_id, "LIFETIME", int(time.time())))
            
            # Skoro wpis przeszedł (nowa faktura), nadajemy dostęp
            upsert_user(telegram_id)
            cursor.execute('UPDATE users SET is_pro = 1, lifetime = 1 WHERE telegram_id = ?', (telegram_id,))
            conn.commit()
            return True # Oznaczono jako nowa i zapłacona
        except sqlite3.IntegrityError:
            return False # Już dodana wcześniej

# Initialize DB on load
init_db()
