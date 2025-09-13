import streamlit as st
import os
import sqlite3
import pandas as pd
from datetime import datetime
from admin_config import DB_PATH

# Database schema definition
REQUIRED_TABLES = {
    "osoblje": {"id", "ime", "sifra", "aktivna"},
    "korisnici": {"id", "ime", "soba"},
    "zone": {"id", "naziv", "korisnik_id", "grace_until"},
    "alarms": {
        "id", "zone_id", "zone_name", "vrijeme", "potvrda",
        "vrijemePotvrde", "korisnik", "soba", "osoblje"
    },
    "comm": {"key", "value"},
}

def table_has_columns(conn, table_name, required_columns):
    """Provjeri ima li tablica sve potrebne kolone"""
    try:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cur.fetchall()}
        return required_columns.issubset(existing_columns)
    except sqlite3.OperationalError:
        return False

def init_database(db_file):
    """Inicijaliziraj bazu podataka s potrebnim tablicama"""
    try:
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        updated_tables = []
        
        for table_name, columns in REQUIRED_TABLES.items():
            if not table_has_columns(conn, table_name, columns):
                updated_tables.append(table_name)
                
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
                        korisnik_id INTEGER,
                        grace_until TIMESTAMP DEFAULT NULL
                    )
                    """)
                    
                    # Dodaj grace_until kolonu ako ne postoji
                    try:
                        cursor.execute("ALTER TABLE zone ADD COLUMN grace_until TIMESTAMP DEFAULT NULL")
                    except sqlite3.OperationalError:
                        pass
                
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
        
        return True, updated_tables
        
    except Exception as e:
        return False, str(e)

# Streamlit app configuration
st.set_page_config(
    page_title="Alarmni Sustav Admin",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide Streamlit menu
st.markdown("""
    <style>
        div[data-testid="stToolbar"] button {
            display: none !important;
        }
        .main > div { padding-top: 2rem; }
    </style>
""", unsafe_allow_html=True)


st.title("🚨 Alarmni Sustav - Admin Panel")

st.markdown("---")

# Database Management
st.subheader("🛠️ Database Management")

if not os.path.exists(DB_PATH):
    st.error("⚠️ Baza podataka ne postoji.")
    if st.button("🚀 Kreiraj novu bazu podataka", type="primary"):
        with st.spinner("Kreiranje baze podataka..."):
            success, result = init_database(DB_PATH)
            if success:
                st.success("✅ Baza podataka uspješno kreirana!")
                if result:
                    st.info(f"Kreirane tablice: {', '.join(result)}")
                st.rerun()
            else:
                st.error(f"❌ Greška pri kreiranju baze: {result}")
    st.stop()

# Check for database updates needed
with sqlite3.connect(DB_PATH) as conn:
    missing_updates = []
    for table_name, required_cols in REQUIRED_TABLES.items():
        if not table_has_columns(conn, table_name, required_cols):
            missing_updates.append(table_name)

if missing_updates:
    st.warning(f"⚠️ Potrebno ažuriranje: {', '.join(missing_updates)}")
    if st.button("🔧 Ažuriraj bazu", type="primary"):
        with st.spinner("Ažuriranje baze podataka..."):
            success, result = init_database(DB_PATH)
            if success:
                if result:
                    st.success("✅ Baza uspješno ažurirana!")
                    st.info(f"Ažurirane tablice: {', '.join(result)}")
                else:
                    st.success("✅ Baza je već ažurna")
                st.rerun()
            else:
                st.error(f"❌ Greška pri ažuriranju: {result}")
else:
    st.success("✅ Baza podataka je ažurna")

# Database statistics
st.subheader("📊 Statistike baze")

def get_table_stats():
    """Dohvati statistike svih tablica"""
    stats = {}
    try:
        with sqlite3.connect(DB_PATH) as conn:
            for table_name in REQUIRED_TABLES.keys():
                try:
                    cur = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    stats[table_name] = cur.fetchone()[0]
                except sqlite3.OperationalError:
                    stats[table_name] = 0
            
            # Grace period check
            try:
                cur = conn.execute("SELECT COUNT(*) FROM zone WHERE grace_until > datetime('now')")
                stats['grace_active'] = cur.fetchone()[0]
            except sqlite3.OperationalError:
                stats['grace_active'] = 0
                
    except Exception as e:
        st.error(f"❌ Greška u statistikama: {e}")
    return stats

stats = get_table_stats()

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("👥 Korisnici", stats.get("korisnici", 0))
with col2:
    st.metric("👩‍⚕️ Osoblje", stats.get("osoblje", 0))
with col3:
    st.metric("🏠 Narukvice", stats.get("zone", 0))
with col4:
    st.metric("🚨 Alarmi", stats.get("alarms", 0))
with col5:
    st.metric("⚙️ Comm", stats.get("comm", 0))

if stats.get('grace_active', 0) > 0:
    st.info(f"⏳ Grace Period: {stats['grace_active']} aktivnih zona")

# System health monitoring
st.subheader("🔍 System Health")

def get_service_status(service_key, timeout=30):
    """Provjeri status servisa preko heartbeat-a"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute("SELECT value FROM comm WHERE key = ?", (f"{service_key}_heartbeat",))
            result = cur.fetchone()
            
            if result:
                heartbeat_time = int(result[0])
                current_time = int(datetime.now().timestamp())
                return "online" if current_time - heartbeat_time < timeout else "offline"
            return "unknown"
    except Exception:
        return "error"

def display_status(name, icon, status):
    """Prikaži status servisa"""
    status_map = {
        "online": ("🟢 Online", "success"),
        "offline": ("🔴 Offline", "error"), 
        "unknown": ("⚪ Unknown", "warning"),
        "error": ("❌ Error", "error")
    }
    text, func = status_map.get(status, ("❓ Unknown", "info"))
    getattr(st, func)(f"{icon} {name}: {text}")

# Get status and display
scanner_status = get_service_status("scanner")
kiosk_status = get_service_status("kiosk", 60)

st.markdown("---")

# Combined status display
col1, col2 = st.columns(2)
with col1:
    display_status("AX PRO Scanner", "📡", scanner_status)
with col2:
    display_status("Kiosk", "📱", kiosk_status)

st.markdown("---")
st.markdown("<sub>© Robert M., 2025 – Admin Panel za Alarmni Sustav</sub>", unsafe_allow_html=True)
