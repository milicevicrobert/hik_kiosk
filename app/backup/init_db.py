import os
import sqlite3

REQUIRED_TABLES = {
    "osoblje": {"id", "ime", "sifra", "aktivna"},
    "korisnici": {"id", "ime", "soba"},
    "zone": {"id", "naziv", "korisnik_id"},
    "alarms": {
        "id", "zone_id", "zone_name", "vrijeme", "potvrda",
        "vrijemePotvrde", "korisnik", "soba", "osoblje"
    },
    "comm": {"key", "value"},
}


def table_has_columns(conn, table_name, required_columns):
    try:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cur.fetchall()}
        return required_columns.issubset(existing_columns)
    except sqlite3.OperationalError:
        return False


def init_baza(db_file="data/alarmni_sustav.db"):
    os.makedirs(os.path.dirname(db_file), exist_ok=True)
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    reinit_required = False

    for table_name, columns in REQUIRED_TABLES.items():
        if not table_has_columns(conn, table_name, columns):
            print(f"🛠️ Stvaranje ili ažuriranje tablice: {table_name}")
            reinit_required = True

            if table_name == "osoblje":
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS osoblje (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ime TEXT NOT NULL,
                    sifra TEXT UNIQUE NOT NULL,
                    aktivna INTEGER DEFAULT 1
                )
                """)

            elif table_name == "korisnici":
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS korisnici (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ime TEXT NOT NULL,
                    soba TEXT
                )
                """)

            elif table_name == "zone":
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS zone (
                    id INTEGER PRIMARY KEY,
                    naziv TEXT NOT NULL,
                    korisnik_id INTEGER
                )
                """)

            elif table_name == "alarms":
                cursor.execute("""
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
                """)

            elif table_name == "comm":
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS comm (
                    key TEXT PRIMARY KEY,
                    value INTEGER DEFAULT 0
                )
                """)
                cursor.execute("""
                    INSERT OR IGNORE INTO comm (key, value)
                    VALUES ('resetAlarm', 0)
                """)

    conn.commit()
    conn.close()

    if reinit_required:
        print(f"✅ Baza ažurirana ili kreirana: {db_file}")
    else:
        print(f"ℹ️ Sve tablice i kolone su već ispravne: {db_file}")


if __name__ == "__main__":
    init_baza()
