# pages/10_DB_admin.py
import os
import sqlite3
import shutil
from datetime import datetime

import pandas as pd
import streamlit as st
from admin_config import DB_PATH

# ====================== PAGE CONFIG & STYLES ======================
st.set_page_config(
    page_title="🗃️ Baza — provjera, inicijalizacija, indeksi & backup",
    page_icon="🗃️",
    layout="wide",
)
st.markdown(
    """
<style>
  div[data-testid="stToolbar"] button { display:none !important; }
  .main > div { padding-top: 2rem; }
  .ok { color: #198754; font-weight: 600; }
  .warn { color: #b58105; font-weight: 600; }
  .err { color: #b02a37; font-weight: 600; }
  .chip { display:inline-block; padding:2px 8px; border-radius:12px; border:1px solid #ddd; margin:0 6px 6px 0; font-size:12px;}
</style>
""",
    unsafe_allow_html=True,
)

st.title("🗃️ Upravljanje bazom (SQLite)")
st.caption(
    "Provjera & inicijalizacija sheme, kreiranje indeksa, optimizacija i backup — s detaljnim logom promjena."
)

# ====================== SCHEMA (zajedničko) ======================
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


# ====================== PRAGMAS & INDEXES ======================
def tune_pragmas(conn: sqlite3.Connection) -> list[str]:
    """Primijeni PRAGMA i vrati log stvarnih vrijednosti."""
    logs = []
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=3000;")
        # conn.execute("PRAGMA foreign_keys=ON;")  # uključi kad uvedeš FK
    except Exception as e:
        logs.append(f"[PRAGMA] Greška: {e}")

    # očitaj efektivne vrijednosti
    try:
        jm = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        sy = conn.execute("PRAGMA synchronous;").fetchone()[0]
        bt = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        logs.append(
            f"[PRAGMA] journal_mode={jm}, synchronous={sy}, busy_timeout={bt} (DB: {DB_PATH})"
        )
    except Exception as e:
        logs.append(f"[PRAGMA] Ne mogu očitati vrijednosti: {e}")
    return logs


# (ime_indeksa, tablica, SQL)
INDEX_DEFS = [
    (
        "ix_alarms_potvrda_vrijeme",
        "alarms",
        "CREATE INDEX IF NOT EXISTS ix_alarms_potvrda_vrijeme ON alarms(potvrda, vrijeme DESC)",
    ),
    (
        "ix_alarms_zone_time",
        "alarms",
        "CREATE INDEX IF NOT EXISTS ix_alarms_zone_time ON alarms(zone_id, vrijeme DESC)",
    ),
    (
        "ux_alarms_active_per_zone",
        "alarms",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_alarms_active_per_zone ON alarms(zone_id) WHERE potvrda=0",
    ),
    (
        "ix_zone_alarm_status",
        "zone",
        "CREATE INDEX IF NOT EXISTS ix_zone_alarm_status ON zone(alarm_status)",
    ),
    (
        "ix_zone_cooldown",
        "zone",
        "CREATE INDEX IF NOT EXISTS ix_zone_cooldown ON zone(cooldown_until)",
    ),
    (
        "ix_zone_korisnik_id",
        "zone",
        "CREATE INDEX IF NOT EXISTS ix_zone_korisnik_id ON zone(korisnik_id)",
    ),
    (
        "ux_osoblje_sifra",
        "osoblje",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_osoblje_sifra ON osoblje(sifra)",
    ),
    (
        "ix_osoblje_sifra_aktivna",
        "osoblje",
        "CREATE INDEX IF NOT EXISTS ix_osoblje_sifra_aktivna ON osoblje(sifra, aktivna)",
    ),
]


# ====================== DB HELPERS ======================
def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    return conn


def get_table_names(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    return [r[0] for r in cur.fetchall()]


def table_has_columns(conn, table_name, required_columns):
    """Provjeri ima li tablica potrebne kolone"""
    try:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cur.fetchall()}
        return required_columns.issubset(existing_columns)
    except sqlite3.OperationalError:
        return False


def table_info(conn: sqlite3.Connection, table_name: str) -> set:
    """Vrati skup postojećih kolona (imena) tablice; prazan skup ako ne postoji."""
    try:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        return set()


def inspect_schema(conn: sqlite3.Connection) -> pd.DataFrame:
    """Pregled sheme: za svaku zahtijevanu tablicu prikaži stanje i nedostajuće kolone."""
    rows = []
    for t, req_cols in REQUIRED_TABLES.items():
        existing_cols = table_info(conn, t)
        exists = len(existing_cols) > 0
        missing = sorted(list(req_cols - existing_cols))
        extra = sorted(list(existing_cols - req_cols)) if exists else []
        rows.append(
            {
                "Tablica": t,
                "Postoji": "DA" if exists else "NE",
                "Nedostajuće kolone": ", ".join(missing) if missing else "",
                "Višak kolone": ", ".join(extra) if extra else "",
                "Broj traženih": len(req_cols),
                "Broj postojećih": len(existing_cols),
            }
        )
    return pd.DataFrame(rows)


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
                soba TEXT,
                zona_id INTEGER
            )
        """
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


def ensure_columns(
    conn: sqlite3.Connection, table_name: str, required_columns: set
) -> list[str]:
    """Doda nedostajuće kolone. Vrati listu dodanih kolona."""
    added = []
    existing = table_info(conn, table_name)
    missing = required_columns - existing
    for col in sorted(missing):
        col_type = TYPE_MAP.get(col, "TEXT")
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type}")
        added.append(f"{table_name}.{col} ({col_type})")
    if added:
        conn.commit()
    return added


def existing_indexes(conn: sqlite3.Connection) -> set:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    return {r[0] for r in cur.fetchall()}


def ensure_indexes(conn: sqlite3.Connection) -> list[str]:
    """Kreira nedostajuće indekse i vrati listu imena koja su kreirana."""
    created = []
    have = existing_indexes(conn)
    cur = conn.cursor()
    for name, table, stmt in INDEX_DEFS:
        if name not in have:
            cur.execute(stmt)
            created.append(f"{name} on {table}")
    if created:
        try:
            conn.execute("ANALYZE;")
        except Exception:
            pass
        conn.commit()
    return created


def get_table_stats(conn: sqlite3.Connection, table_name: str) -> int:
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        return int(cur.fetchone()[0])
    except Exception:
        return 0


def get_table_data(conn: sqlite3.Connection, table_name: str) -> pd.DataFrame:
    return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


def vacuum_analyze() -> tuple[int, int]:
    """VACUUM + ANALYZE; vrati veličine (KB) prije i poslije."""
    exists = os.path.exists(DB_PATH)
    before_kb = int(os.path.getsize(DB_PATH) / 1024) if exists else 0
    with connect() as conn:
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
        conn.commit()
    after_kb = int(os.path.getsize(DB_PATH) / 1024) if exists else 0
    return before_kb, after_kb


def backup_database() -> str | None:
    """Napraviti backup u /backup; vrati punu putanju backup datoteke."""
    try:
        backup_dir = os.path.join(os.path.dirname(DB_PATH), "backup")
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(backup_dir, f"backup_{ts}.db")
        shutil.copy2(DB_PATH, dst)
        return dst
    except Exception as e:
        st.error(f"Greška pri backupu: {e}")
        return None


# ====================== SUMMARY (zaglavlje) ======================
exists = os.path.exists(DB_PATH)
col1, col2 = st.columns([8, 2])  # 80% / 20%

with col1:
    st.metric(
        "💾 Baza",
        os.path.join(os.path.dirname(DB_PATH), os.path.basename(DB_PATH)),
        "OK" if exists else "NE",
    )

with col2:
    size_kb = (os.path.getsize(DB_PATH) / 1024) if exists else 0
    st.metric("📦 Veličina (KB)", f"{size_kb:.1f}")

st.divider()

# ====================== TABS ======================
tab1, tab2, tab3 = st.tabs(
    [
        "🔍 Provjera & Inicijalizacija (s backupom)",
        "📋 Pregled tablica",
        "📊 Analitika & Optimizacija",
    ]
)

# ---------- TAB 1: Provjera & Inicijalizacija ----------
with tab1:
    st.subheader("📊 Trenutni status sheme")
    if not exists:
        st.warning(f"Baza ne postoji: {DB_PATH}")
        st.info("Klikni **Inicijaliziraj / popravi** za stvaranje.")
    else:
        with connect() as conn:
            df_status = inspect_schema(conn)
        st.dataframe(df_status, width='stretch', hide_index=True)

        # Vizualna oznaka nedostajućih kolona po tablici
        for _, row in df_status.iterrows():
            missing = [
                c.strip() for c in row["Nedostajuće kolone"].split(",") if c.strip()
            ]
            if missing:
                chips = " ".join([f"<span class='chip'>{c}</span>" for c in missing])
                st.markdown(
                    f"**{row['Tablica']}** → Nedostaju: {chips}", unsafe_allow_html=True
                )

    st.markdown("---")

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
    if st.button(
        "🔄 Inicijaliziraj / popravi (tablice, kolone, indeksi) — i prikaži log",
        width='stretch',
    ):
        logs = []
        # Kreiraj datoteku ako nedostaje
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        if not os.path.exists(DB_PATH):
            open(DB_PATH, "a").close()
            logs.append(f"[FILE] Kreirana prazna baza: {DB_PATH}")

        with connect() as conn:
            # PRAGMA (i izvještaj)
            logs += tune_pragmas(conn)

            # 1) Kreiraj tablice koje ne postoje
            created_tables = []
            for t in REQUIRED_TABLES.keys():
                if ensure_table(conn, t):
                    created_tables.append(t)
                    logs.append(f"[TABLE] Kreirana tablica: {t} (DB: {DB_PATH})")

            # 2) Dodaj nedostajuće kolone
            added_cols_total = 0
            for t, cols in REQUIRED_TABLES.items():
                added = ensure_columns(conn, t, cols)
                if added:
                    added_cols_total += len(added)
                    for col in added:
                        logs.append(f"[COLUMN] Dodana kolona: {col} (DB: {DB_PATH})")

            # 3) Indeksi
            created_idx = ensure_indexes(conn)
            for i in created_idx:
                logs.append(f"[INDEX] Kreiran indeks: {i} (DB: {DB_PATH})")
            if not created_idx:
                logs.append("[INDEX] Nema novih indeksa — svi već postoje.")

        # Rezime
        if created_tables:
            logs.append(
                f"[SUMMARY] Kreirano tablica: {len(created_tables)} → {', '.join(created_tables)}"
            )
        else:
            logs.append("[SUMMARY] Nema novih tablica.")
        logs.append(f"[SUMMARY] Dodano kolona: {added_cols_total}")
        st.success("✅ Inicijalizacija / popravak dovršen. Detaljni log ispod.")
        st.code("\n".join(logs))

    if st.button("💾 Napravi backup i prikaži putanju", width='stretch'):
        if not os.path.exists(DB_PATH):
            st.error("Baza ne postoji — nema što backupirati.")
        else:
            path = backup_database()
            if path:
                size_b = os.path.getsize(path) / 1024
                st.success(f"✅ Backup kreiran ({size_b:.1f} KB)")
                st.code(path)


# ---------- TAB 2: Pregled tablica ----------
with tab2:
    st.markdown("### 📂 Odaberi tablicu za prikaz")
    if not exists:
        st.warning(
            "⚠️ Baza ne postoji. Pokreni inicijalizaciju u tabu 'Provjera & Inicijalizacija'."
        )
    else:
        with connect() as conn:
            tables = get_table_names(conn)
            if not tables:
                st.info("🔍 Nema tablica u bazi.")
            else:
                selected = st.selectbox(
                    "Tablica", tables, index=0, key="table_selector"
                )
                if selected:
                    colA, colB = st.columns([2, 1])
                    with colA:
                        st.markdown(f"#### 📄 `{selected}`")
                    with colB:
                        st.metric("Broj zapisa", get_table_stats(conn, selected))

                    df = get_table_data(conn, selected)
                    if df.empty:
                        st.info(f"📭 Tablica `{selected}` je prazna.")
                    else:
                        colX, colY = st.columns([3, 1])
                        with colY:
                            show_all = st.checkbox(
                                "Prikaži sve zapise", value=len(df) <= 100
                            )
                        if show_all or len(df) <= 100:
                            st.dataframe(df, width='stretch', height=420)
                        else:
                            st.dataframe(
                                df.head(100), width='stretch', height=420
                            )
                            st.info(
                                f"Prikazano prvih 100 od {len(df)} zapisa. Označi 'Prikaži sve zapise' za sve."
                            )

                        csv = df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            label=f"📥 Preuzmi {selected}.csv",
                            data=csv,
                            file_name=f"{selected}.csv",
                            mime="text/csv",
                            width='stretch',
                        )

# ---------- TAB 3: Analitika & Optimizacija ----------
with tab3:
    st.markdown("### 📈 Pregled veličina tablica & optimizacija")
    if not exists:
        st.warning("⚠️ Baza ne postoji.")
    else:
        with connect() as conn:
            tnames = get_table_names(conn)
            if tnames:
                rows = [
                    {"Tablica": t, "Broj zapisa": get_table_stats(conn, t)}
                    for t in tnames
                ]
                df_sizes = pd.DataFrame(rows)
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.dataframe(df_sizes, width='stretch', hide_index=True)
                with c2:
                    if not df_sizes.empty and df_sizes["Broj zapisa"].sum() > 0:
                        st.bar_chart(df_sizes.set_index("Tablica")["Broj zapisa"])

        st.markdown("#### 🧹 VACUUM + ANALYZE (s izvještajem)")
        if st.button("Pokreni i prikaži uštedu", width='stretch'):
            before_kb, after_kb = vacuum_analyze()
            delta = before_kb - after_kb
            if delta >= 0:
                st.success(
                    f"✅ VACUUM/ANALYZE završeno. Veličina: {before_kb} KB → {after_kb} KB (ušteda {delta} KB). DB: {DB_PATH}"
                )
            else:
                st.info(
                    f"ℹ️ Veličina se povećala (npr. novi page cache/statistike): {before_kb} KB → {after_kb} KB. DB: {DB_PATH}"
                )

        st.markdown("#### 🚨 Alarmi / 📿 Zone (brza analitika)")
        with connect() as conn:
            tnames = get_table_names(conn)
            if "alarms" in tnames:
                alarms_df = get_table_data(conn, "alarms")
                if not alarms_df.empty:
                    a1, a2, a3 = st.columns(3)
                    total = len(alarms_df)
                    confirmed = int((alarms_df["potvrda"] == 1).sum())
                    with a1:
                        st.metric("Ukupno alarma", total)
                    with a2:
                        st.metric("Potvrđeni", confirmed)
                    with a3:
                        st.metric("Nepotvrđeni", total - confirmed)
                else:
                    st.info("Nema podataka o alarmima.")
            if "zone" in tnames:
                zone_df = get_table_data(conn, "zone")
                if not zone_df.empty:
                    z1, z2 = st.columns(2)
                    total_zones = len(zone_df)
                    assigned = int(zone_df["korisnik_id"].notna().sum())
                    with z1:
                        st.metric("Ukupno narukvica", total_zones)
                        st.metric("Dodijeljene narukvice", assigned)
                    with z2:
                        free = total_zones - assigned
                        st.metric("Slobodne narukvice", free)
                        if total_zones > 0:
                            st.metric(
                                "Postotak korištenja",
                                f"{(assigned/total_zones)*100:.1f}%",
                            )

st.markdown("---")
st.markdown(
    '<div style="text-align:right; color:gray; font-size:0.85em;">DB Admin v4.0 | © RM 2025</div>',
    unsafe_allow_html=True,
)
