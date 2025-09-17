import os
import sqlite3
import streamlit as st
import pandas as pd
from admin_config import DB_PATH

# Page configuration
st.set_page_config(page_title="Baza podataka", page_icon="🗃️", layout="wide")

# Hide Streamlit menu
st.markdown(
    """
    <style>
        div[data-testid="stToolbar"] button {
            display: none !important;
        }
        .main > div { padding-top: 2rem; }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("🗃️ Upravljanje Bazom Podataka")
st.caption("Provjera, inicijalizacija i pregled podataka")

# Database configuration
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


# Database utility functions
def table_has_columns(conn, table_name, required_columns):
    """Provjeri ima li tablica potrebne kolone"""
    try:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cur.fetchall()}
        return required_columns.issubset(existing_columns)
    except sqlite3.OperationalError:
        return False


def get_table_names(conn):
    """Dohvati nazive svih tablica"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [t[0] for t in cursor.fetchall()]


def get_table_data(conn, table_name):
    """Dohvati sve podatke iz tablice"""
    return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


def get_table_stats(conn, table_name):
    """Dohvati statistike tablice"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        return count
    except Exception:
        return 0


def init_database(db_file=DB_PATH):
    """Inicijaliziraj/stvori potrebne tablice"""
    os.makedirs(os.path.dirname(db_file), exist_ok=True)
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    missing_tables = []

    for table_name, columns in REQUIRED_TABLES.items():
        if not table_has_columns(conn, table_name, columns):
            missing_tables.append(table_name)

            if table_name == "osoblje":
                cursor.execute(
                    """
                CREATE TABLE IF NOT EXISTS osoblje (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ime TEXT NOT NULL,
                    sifra TEXT UNIQUE NOT NULL,
                    aktivna INTEGER DEFAULT 1
                )
                """
                )

            elif table_name == "korisnici":
                cursor.execute(
                    """
                CREATE TABLE IF NOT EXISTS korisnici (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ime TEXT NOT NULL,
                    soba TEXT,
                    zona_id INTEGER 
                )
                """
                )

            elif table_name == "zone":
                cursor.execute(
                    """
                CREATE TABLE IF NOT EXISTS zone (
                    id INTEGER PRIMARY KEY,
                    naziv TEXT NOT NULL,
                    korisnik_id INTEGER,
                    alarm_status INTEGER DEFAULT 0,
                    last_updated TEXT DEFAULT NULL,
                    last_alarm_time TEXT DEFAULT NULL

                )
                """
                )

            elif table_name == "alarms":
                cursor.execute(
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

            elif table_name == "comm":
                cursor.execute(
                    """
                CREATE TABLE IF NOT EXISTS comm (
                    key TEXT PRIMARY KEY,
                    value INTEGER DEFAULT 0
                )
                """
                )
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO comm (key, value)
                    VALUES ('resetAlarm', 0)
                """
                )

    conn.commit()
    conn.close()
    return missing_tables


def ensure_table_columns(conn, table_name, required_columns):
    """Dodaje nedostajuće kolone u tablicu prema REQUIRED_TABLES"""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cur.fetchall()}

    # Mapiranje tipova po imenu kolone (prilagodite prema potrebi)
    type_map = {
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
    }

    for col in required_columns - existing_columns:
        col_type = type_map.get(col, "TEXT")
        try:
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type}")
            print(f"✅ Dodana kolona '{col}' u tablicu '{table_name}'")
        except Exception as e:
            print(f"❌ Greška pri dodavanju kolone '{col}' u '{table_name}': {e}")

    conn.commit()


def clear_table_data(table_name):
    """Obriši sve podatke iz tablice"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(f"DELETE FROM {table_name}")
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri brisanju tablice {table_name}: {e}")
        return False


def backup_database():
    """Stvori backup baze podataka"""
    import shutil
    from datetime import datetime

    try:
        backup_dir = os.path.join(os.path.dirname(DB_PATH), "backup")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")

        shutil.copy2(DB_PATH, backup_path)
        return backup_path
    except Exception as e:
        st.error(f"Greška pri stvaranju backup-a: {e}")
        return None


# ===================== STREAMLIT UI =====================

# Database status overview
st.markdown("### 📊 Status Baze Podataka")

col1, col2, col3 = st.columns(3)

with col1:
    if os.path.exists(DB_PATH):
        db_size = os.path.getsize(DB_PATH) / 1024  # KB
        st.metric("💾 Baza podataka", f"{db_size:.1f} KB", "Postoji")
    else:
        st.metric("💾 Baza podataka", "Ne postoji", "❌")

with col2:
    if os.path.exists(DB_PATH):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                table_count = len(get_table_names(conn))
            st.metric("📋 Broj tablica", table_count)
        except:
            st.metric("📋 Broj tablica", "Greška", "❌")
    else:
        st.metric("📋 Broj tablica", 0)

with col3:
    if os.path.exists(DB_PATH):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                total_records = sum(
                    get_table_stats(conn, table) for table in get_table_names(conn)
                )
            st.metric("📝 Ukupno zapisa", total_records)
        except:
            st.metric("📝 Ukupno zapisa", "Greška", "❌")
    else:
        st.metric("📝 Ukupno zapisa", 0)

st.markdown("---")

# Tabs for different functionalities
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🔧 Provjera & Inicijalizacija",
        "📋 Pregled Tablica",
        "🛠️ Održavanje",
        "📊 Analiza",
    ]
)

# Tab 1: Database Check & Initialization
with tab1:
    st.markdown("### 🔍 Provjera Tablica")

    if not os.path.exists(DB_PATH):
        st.error(f"❌ Baza ne postoji: {DB_PATH}")
        st.info("💡 Koristite gumb 'Inicijaliziraj bazu' za stvaranje")
    else:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                all_ok = True
                for table_name, columns in REQUIRED_TABLES.items():
                    if table_has_columns(conn, table_name, columns):
                        st.success(f"✅ **{table_name}** - sve kolone prisutne")
                    else:
                        st.warning(
                            f"⚠️ **{table_name}** - nedostaju kolone ili tablica ne postoji"
                        )
                        all_ok = False

                if all_ok:
                    st.success("🎉 Sve tablice su ispravno konfigurirane!")

        except Exception as e:
            st.error(f"Greška pri čitanju baze: {e}")

    st.markdown("### ⚙️ Akcije")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Inicijaliziraj/Popravi Bazu", width="stretch"):
            with st.spinner("Inicijaliziram bazu..."):
                missing_tables = init_database()
                with sqlite3.connect(DB_PATH) as conn:
                    for table_name, columns in REQUIRED_TABLES.items():
                        ensure_table_columns(conn, table_name, columns)

                if missing_tables:
                    st.success(
                        f"✅ Tablice stvorene/ažurirane: {', '.join(missing_tables)}"
                    )
                else:
                    st.info("ℹ️ Sve tablice već postoje i ispravne su")

    with col2:
        if st.button("💾 Stvori Backup", width="stretch"):
            with st.spinner("Stvaram backup..."):
                backup_path = backup_database()
                if backup_path:
                    st.success(f"✅ Backup stvoren: {os.path.basename(backup_path)}")

# Tab 2: Table Viewing
with tab2:
    st.markdown("### 📋 Pregled Podataka")

    if not os.path.exists(DB_PATH):
        st.warning("⚠️ Baza ne postoji")
    else:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                tables = get_table_names(conn)

                if not tables:
                    st.info("🔍 Baza je prazna (nema tablica)")
                else:
                    # Table selector
                    selected_table = st.selectbox(
                        "📂 Odaberi tablicu za prikaz:", tables, key="table_selector"
                    )

                    if selected_table:
                        # Table statistics
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.markdown(f"#### 📄 Tablica: `{selected_table}`")
                        with col2:
                            record_count = get_table_stats(conn, selected_table)
                            st.metric("Broj zapisa", record_count)

                        # Display data
                        df = get_table_data(conn, selected_table)

                        if df.empty:
                            st.info(f"📭 Tablica `{selected_table}` je prazna")
                        else:
                            # Options for display
                            col1, col2 = st.columns([3, 1])
                            with col2:
                                show_all = st.checkbox(
                                    "Prikaži sve zapise", value=len(df) <= 100
                                )

                            if show_all or len(df) <= 100:
                                st.dataframe(df, width="stretch", height=400)
                            else:
                                st.dataframe(df.head(100), width="stretch", height=400)
                                st.info(
                                    f"Prikazano prvih 100 od {len(df)} zapisa. Označite 'Prikaži sve zapise' za prikaz svih."
                                )

                            # Download option
                            csv = df.to_csv(index=False).encode("utf-8")
                            st.download_button(
                                label=f"📥 Preuzmi {selected_table}.csv",
                                data=csv,
                                file_name=f"{selected_table}.csv",
                                mime="text/csv",
                            )

        except Exception as e:
            st.error(f"Greška pri čitanju baze: {e}")

# Tab 3: Maintenance
with tab3:
    st.markdown("### 🛠️ Održavanje Baze")
    st.warning("⚠️ Ove operacije mogu biti nepovratne!")

    if os.path.exists(DB_PATH):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                tables = get_table_names(conn)

                if tables:
                    st.markdown("#### 🗑️ Brisanje Podataka")

                    selected_table_clear = st.selectbox(
                        "Odaberi tablicu za brisanje podataka:",
                        [""] + tables,
                        key="clear_table_selector",
                    )

                    if selected_table_clear:
                        record_count = get_table_stats(conn, selected_table_clear)
                        st.warning(
                            f"Tablica `{selected_table_clear}` ima {record_count} zapisa"
                        )

                        if st.button(
                            f"🗑️ Obriši sve podatke iz `{selected_table_clear}`",
                            type="secondary",
                        ):
                            if clear_table_data(selected_table_clear):
                                st.success(
                                    f"✅ Svi podaci iz tablice `{selected_table_clear}` su obrisani"
                                )
                                st.rerun()

                    st.markdown("#### 📊 Optimizacija")
                    if st.button("🔧 Optimiziraj bazu podataka", width="stretch"):
                        try:
                            with sqlite3.connect(DB_PATH) as conn:
                                conn.execute("VACUUM")
                                conn.commit()
                            st.success("✅ Baza optimizirana")
                        except Exception as e:
                            st.error(f"Greška pri optimizaciji: {e}")

        except Exception as e:
            st.error(f"Greška: {e}")
    else:
        st.info("Baza ne postoji")

# Tab 4: Analysis
with tab4:
    st.markdown("### 📊 Analiza Podataka")

    if not os.path.exists(DB_PATH):
        st.warning("⚠️ Baza ne postoji")
    else:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                # Table size analysis
                st.markdown("#### 📈 Veličina Tablica")
                tables = get_table_names(conn)

                if tables:
                    table_data = []
                    for table in tables:
                        count = get_table_stats(conn, table)
                        table_data.append({"Tablica": table, "Broj zapisa": count})

                    df_analysis = pd.DataFrame(table_data)

                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.dataframe(df_analysis, width="stretch")
                    with col2:
                        if (
                            not df_analysis.empty
                            and df_analysis["Broj zapisa"].sum() > 0
                        ):
                            st.bar_chart(
                                df_analysis.set_index("Tablica")["Broj zapisa"]
                            )

                    # Specific analysis for alarm data
                    if "alarms" in tables:
                        st.markdown("#### 🚨 Analiza Alarma")

                        alarms_df = get_table_data(conn, "alarms")
                        if not alarms_df.empty:
                            col1, col2, col3 = st.columns(3)

                            with col1:
                                total_alarms = len(alarms_df)
                                st.metric("Ukupno alarma", total_alarms)

                            with col2:
                                confirmed = len(alarms_df[alarms_df["potvrda"] == 1])
                                st.metric("Potvrđeni alarmi", confirmed)

                            with col3:
                                unconfirmed = total_alarms - confirmed
                                st.metric("Nepotvrđeni alarmi", unconfirmed)
                        else:
                            st.info("Nema podataka o alarmima")

                    # Zone usage analysis
                    if "zone" in tables and "korisnici" in tables:
                        st.markdown("#### 📿 Analiza Narukvica")

                        zone_df = get_table_data(conn, "zone")
                        if not zone_df.empty:
                            col1, col2 = st.columns(2)

                            with col1:
                                total_zones = len(zone_df)
                                assigned_zones = len(
                                    zone_df[zone_df["korisnik_id"].notna()]
                                )
                                st.metric("Ukupno narukvica", total_zones)
                                st.metric("Dodijeljene narukvice", assigned_zones)

                            with col2:
                                free_zones = total_zones - assigned_zones
                                st.metric("Slobodne narukvice", free_zones)
                                if total_zones > 0:
                                    usage_percent = (assigned_zones / total_zones) * 100
                                    st.metric(
                                        "Postotak korištenja", f"{usage_percent:.1f}%"
                                    )
                else:
                    st.info("Nema tablica za analizu")

        except Exception as e:
            st.error(f"Greška pri analizi: {e}")

# Footer
st.markdown("---")
st.markdown(
    '<div style="text-align:right; color:gray; font-size:0.85em;">🗃️ Database Management v2.0 | © RM 2025</div>',
    unsafe_allow_html=True,
)
