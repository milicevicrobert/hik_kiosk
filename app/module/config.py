import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "alarmni_sustav.db")
SOUND_FILE = os.path.join(os.path.dirname(__file__), "test_alarm.mp3")
PIN = int(4)  # broj znamenki PIN-a
TIME_FMT = "%Y-%m-%d %H:%M:%S"
REQUIRED_TABLES = {
    "osoblje": {"id", "ime", "sifra", "aktivna"},
    "korisnici": {"id", "ime", "soba", "zona_id"},
    "zone": {
        "id",
        "naziv",
        "korisnik_id",
        "alarm_status",
        "last_updated",
        "last_alarm_time",
        "cooldown_until_epoch",
        "cooldown_until",
    },
    "alarms": {
        "id",
        "zone_id",
        "zone_name",
        "vrijeme",
        "potvrda",
        "vrijemePotvrde",
        "korisnik",
        "soba",
        "osoblje",
    },
    "comm": {"key", "value"},
}

TYPE_MAP = {
    "id": "INTEGER",
    "ime": "TEXT",
    "sifra": "TEXT",
    "aktivna": "INTEGER",
    "soba": "TEXT",
    "zona_id": "INTEGER",
    "korisnik_id": "INTEGER",
    "alarm_status": "INTEGER DEFAULT 0",
    "last_updated": "TEXT DEFAULT NULL",
    "last_alarm_time": "TEXT DEFAULT NULL",
    "zone_name": "TEXT",
    "vrijeme": "TEXT",
    "potvrda": "INTEGER DEFAULT 0",
    "vrijemePotvrde": "TEXT",
    "korisnik": "TEXT",
    "osoblje": "TEXT",
    "key": "TEXT",
    "value": "INTEGER DEFAULT 0",
    "cooldown_until_epoch": "INTEGER DEFAULT 0",
    "cooldown_until": "TEXT DEFAULT NULL",
}


def table_info(conn: sqlite3.Connection, table_name: str) -> set:
    """Vrati skup postojećih kolona (imena) tablice; prazan skup ako ne postoji."""
    try:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        return set()


def ensure_table(conn: sqlite3.Connection, name: str) -> bool:
    """Kreira tablicu ako ne postoji. Vrati True ako je kreirana."""
    created = False
    cur = conn.cursor()
    existing = table_info(conn, name)
    if existing:
        return False

    if name == "osoblje":
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS osoblje (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ime TEXT NOT NULL,
                sifra TEXT UNIQUE NOT NULL,
                aktivna INTEGER DEFAULT 1
            )
        """
        )
        created = True
    elif name == "korisnici":
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS korisnici (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ime TEXT NOT NULL,
                soba TEXT
                )"""
        )
        created = True
    elif name == "zone":
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS zone (
                id INTEGER PRIMARY KEY,
                naziv TEXT NOT NULL,
                korisnik_id INTEGER,
                alarm_status INTEGER DEFAULT 0,
                last_updated TEXT DEFAULT NULL,
                last_alarm_time TEXT DEFAULT NULL,
                cooldown_until_epoch INTEGER DEFAULT 0
            )
        """
        )
        created = True
    elif name == "alarms":
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS alarms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                zone_name TEXT NOT NULL,
                vrijeme TEXT NOT NULL,
                potvrda INTEGER DEFAULT 0,
                vrijemePotvrde TEXT,
                korisnik TEXT,
                soba TEXT,
                osoblje TEXT
            )
        """
        )
        created = True
    elif name == "comm":
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS comm (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """
        )
        cur.execute("INSERT OR IGNORE INTO comm(key,value) VALUES('resetAlarm',0)")
        created = True

    if created:
        conn.commit()
    return created
