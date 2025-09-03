import os
import sqlite3
import streamlit as st
from admin_config import DB_PATH

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


def init_baza(db_file=DB_PATH):
    os.makedirs(os.path.dirname(db_file), exist_ok=True)
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    missing_info = []

    for table_name, columns in REQUIRED_TABLES.items():
        if not table_has_columns(conn, table_name, columns):
            missing_info.append(table_name)

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
    return missing_info


# ---------------------- STREAMLIT UI ----------------------

st.title("🛠️ Provjera i inicijalizacija baze podataka")

if not os.path.exists(DB_PATH):
    st.error(f"Baza ne postoji: {DB_PATH}")
else:
    st.success(f"Baza pronađena: {DB_PATH}")

with st.expander("Status tablica u bazi", expanded=True):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            for table_name, columns in REQUIRED_TABLES.items():
                if table_has_columns(conn, table_name, columns):
                    st.markdown(f"✅ **{table_name}** — sve kolone OK")
                else:
                    st.warning(f"⚠️ {table_name} — nedostaju polja ili tablica ne postoji")
    except Exception as e:
        st.error(f"Greška pri čitanju baze: {e}")

if st.button("🔄 Stvori / popravi tablice"):
    nedostaju = init_baza()
    if nedostaju:
        st.warning(f"Tablice ažurirane ili stvorene: {', '.join(nedostaju)}")
    else:
        st.success("Sve tablice i kolone su već ispravne.")
