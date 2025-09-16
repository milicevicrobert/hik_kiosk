import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

try:
    from axpro.axpro_auth import (
        login_axpro,
        get_zone_status,
        clear_axpro_alarms,
        HOST,
        USERNAME,
        PASSWORD,
    )
    from axpro.ax_config import DB_PATH

    AXPRO_AVAILABLE = True
except ImportError as e:
    st.error(f"❌ Greška pri učitavanju Axpro modula: {e}")
    AXPRO_AVAILABLE = False
    DB_PATH = "data/alarmni_sustav.db"  # Fallback

# Page configuration
st.set_page_config(page_title="Zone Sync", page_icon="🔄", layout="wide")

# Hide Streamlit menu
st.markdown(
    """
    <style>
        div[data-testid="stToolbar"] button {
            display: none !important;
        }
        .main > div { padding-top: 2rem; }
        .stAlert > div { border-radius: 10px; }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("🔄 Sinkronizacija i testiranje Axpro centrale")
st.caption("Dohvaćanje zona, sinkronizacija i testiranje komunikacije")

# Initialize session state
if "sync_log" not in st.session_state:
    st.session_state.sync_log = []
if "last_sync" not in st.session_state:
    st.session_state.last_sync = None


def log_message(message, type="info"):
    """Dodaj poruku u log"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.sync_log.append(
        {"time": timestamp, "message": message, "type": type}
    )


def get_zone_iz_baze():
    """Dohvati zone iz baze podataka"""
    try:
        if not os.path.exists(DB_PATH):
            return pd.DataFrame()

        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(
                """
                SELECT z.id, z.naziv, z.korisnik_id, k.ime as korisnik_ime
                FROM zone z
                LEFT JOIN korisnici k ON z.korisnik_id = k.id
                ORDER BY z.id
                """,
                conn,
            )
    except Exception as e:
        st.error(f"❌ Greška pri čitanju baze: {e}")
        return pd.DataFrame()


def get_zone_status_detailed():
    """Dohvati detaljan status zona s centrale (kao u testnoj stranici)"""
    if not AXPRO_AVAILABLE:
        return None

    try:
        with st.spinner("🔄 Dohvaćam status zona..."):
            cookie = login_axpro()
            zones_data = get_zone_status(cookie)
            zone_list = [z["Zone"] for z in zones_data.get("ZoneList", [])]
            log_message(f"📊 Dohvaćen detaljan status {len(zone_list)} zona", "info")
            return zone_list
    except Exception as e:
        log_message(f"❌ Greška pri dohvaćanju statusa zona: {e}", "error")
        st.error(f"❌ Greška: {e}")
        return None


def reset_alarme_na_centrali():
    """Resetiraj sve alarme na centrali (kao u testnoj stranici)"""
    if not AXPRO_AVAILABLE:
        return False, "Axpro moduli nisu dostupni"

    try:
        with st.spinner("🧹 Resetiram alarme..."):
            cookie = login_axpro()
            status, response_text = clear_axpro_alarms(cookie)
            log_message(f"🧯 Alarmi resetirani (status: {status})", "success")
            return True, response_text
    except Exception as e:
        log_message(f"❌ Greška pri resetiranju alarma: {e}", "error")
        return False, str(e)


def sinkroniziraj_zone():
    """Sinkroniziraj zone s centrale u bazu"""
    if not AXPRO_AVAILABLE:
        return 0, 0, 0

    try:
        with st.spinner("🔄 Sinkronizacija zona..."):
            cookie = login_axpro()
            zones_data = get_zone_status(cookie)
            zone_list = [z["Zone"] for z in zones_data.get("ZoneList", [])]

            if not zone_list:
                log_message("⚠️ Nema zona za sinkronizaciju", "warning")
                return 0, 0, 0

            # Upiši u bazu
            return upisi_zone_u_bazu([(z["id"], z["name"]) for z in zone_list])

    except Exception as e:
        log_message(f"❌ Greška pri sinkronizaciji: {e}", "error")
        st.error(f"❌ Greška pri sinkronizaciji: {e}")
        return 0, 0, 0


def upisi_zone_u_bazu(zone_podaci, update_existing=False):
    """Upiši zone u bazu podataka"""
    if not zone_podaci:
        log_message("⚠️ Nema zona za upis", "warning")
        return 0, 0, 0

    if not os.path.exists(DB_PATH):
        log_message("❌ Baza ne postoji", "error")
        st.error(f"❌ Baza podataka ne postoji: {DB_PATH}")
        return 0, 0, 0

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()

            # Osiguraj da postoji tablica zone
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS zone (
                    id INTEGER PRIMARY KEY, 
                    naziv TEXT NOT NULL, 
                    korisnik_id INTEGER
                )
            """
            )

            nove_zone = 0
            azurirane_zone = 0
            neizmijenjene_zone = 0

            for zona_id, naziv in zone_podaci:
                cur.execute("SELECT naziv FROM zone WHERE id = ?", (zona_id,))
                postojeca = cur.fetchone()

                if not postojeca:
                    # Nova zona
                    cur.execute(
                        "INSERT INTO zone (id, naziv) VALUES (?, ?)", (zona_id, naziv)
                    )
                    log_message(f"✅ Dodana nova zona: {zona_id} – {naziv}", "success")
                    nove_zone += 1

                elif postojeca[0] != naziv and update_existing:
                    # Ažuriraj postojeću zonu
                    cur.execute(
                        "UPDATE zone SET naziv = ? WHERE id = ?", (naziv, zona_id)
                    )
                    log_message(
                        f"🔄 Ažurirana zona: {zona_id} – {postojeca[0]} → {naziv}",
                        "info",
                    )
                    azurirane_zone += 1

                else:
                    # Zona postoji i nije promijenjena
                    neizmijenjene_zone += 1

            conn.commit()

            if nove_zone == 0 and azurirane_zone == 0:
                log_message("ℹ️ Sve zone već postoje u bazi", "info")
            else:
                log_message(
                    f"🎯 Sinkronizacija završena: {nove_zone} novih, {azurirane_zone} ažuriranih",
                    "success",
                )

            return nove_zone, azurirane_zone, neizmijenjene_zone

    except Exception as e:
        log_message(f"❌ Greška pri upisu u bazu: {e}", "error")
        st.error(f"❌ Greška pri upisu u bazu: {e}")
        return 0, 0, 0


def obrisi_zonu_iz_baze(zona_id):
    """Obriši zonu iz baze"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()

            # Provjeri ima li zona dodijeljenog korisnika
            cur.execute("SELECT korisnik_id FROM zone WHERE id = ?", (zona_id,))
            result = cur.fetchone()

            if result and result[0]:
                st.error("❌ Ne mogu obrisati zonu koja ima dodijeljenog korisnika!")
                return False

            # Obriši zonu
            cur.execute("DELETE FROM zone WHERE id = ?", (zona_id,))
            conn.commit()

            if cur.rowcount > 0:
                log_message(f"🗑️ Obrisana zona: {zona_id}", "info")
                return True
            else:
                st.warning("⚠️ Zona nije pronađena!")
                return False

    except Exception as e:
        st.error(f"❌ Greška pri brisanju zone: {e}")
        return False


# Status provjera
if not os.path.exists(DB_PATH):
    st.error(f"❌ Baza podataka ne postoji: {DB_PATH}")
    st.stop()

if not AXPRO_AVAILABLE:
    st.warning("⚠️ Axpro moduli nisu dostupni. Možete samo pregledavati postojeće zone.")

# Tabs za organizaciju
tab1, tab2, tab3 = st.tabs(
    ["📊 Zone u bazi", "🔄 Sinkronizacija", "🧪 Testiranje centrale"]
)

with tab1:
    st.subheader("📊 Zone u bazi podataka")

    zone_df = get_zone_iz_baze()

    if zone_df.empty:
        st.info("ℹ️ Nema zona u bazi podataka.")
    else:
        # Statistike
        ukupno_zona = len(zone_df)
        dodijeljene = len(zone_df[zone_df["korisnik_id"].notna()])
        slobodne = ukupno_zona - dodijeljene

        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("📍 Ukupno zona", ukupno_zona)
        with col_stat2:
            st.metric("🟢 Dodijeljene", dodijeljene)
        with col_stat3:
            st.metric("⚪ Slobodne", slobodne)

        # Tablica zona
        st.dataframe(
            zone_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", width="small"),
                "naziv": st.column_config.TextColumn("Naziv zone"),
                "korisnik_id": st.column_config.NumberColumn(
                    "Korisnik ID", width="small"
                ),
                "korisnik_ime": st.column_config.TextColumn("Korisnik"),
            },
            use_container_width=True,
            hide_index=True,
        )

        # Opcije za brisanje zona
        with st.expander("🗑️ Obriši zonu"):
            st.warning(
                "⚠️ Možete obrisati samo zone koje nemaju dodijeljenog korisnika!"
            )

            slobodne_zone = zone_df[zone_df["korisnik_id"].isna()]
            if slobodne_zone.empty:
                st.info("ℹ️ Nema slobodnih zona za brisanje.")
            else:
                zona_za_brisanje = st.selectbox(
                    "Odaberi zonu za brisanje:",
                    options=slobodne_zone["id"].tolist(),
                    format_func=lambda x: f"Zona {x}: {slobodne_zone[slobodne_zone['id'] == x]['naziv'].iloc[0]}",
                )

                if st.button("🗑️ Obriši zonu", type="secondary"):
                    if obrisi_zonu_iz_baze(zona_za_brisanje):
                        st.success("✅ Zona obrisana!")
                        st.rerun()

with tab2:
    st.subheader("🔄 Sinkronizacija s centralom")

    if st.session_state.last_sync:
        st.info(f"⏰ Zadnja sinkronizacija: {st.session_state.last_sync}")

    # Opcije sinkronizacije
    update_existing = st.checkbox(
        "📝 Ažuriraj postojeće zone",
        help="Ažuriraj nazive postojećih zona ako su promijenjeni na centrali",
    )

    # Gumb za sinkronizaciju
    if st.button(
        "🔄 Sinkroniziraj zone s centrale",
        disabled=not AXPRO_AVAILABLE,
        use_container_width=True,
    ):
        nove, azurirane, neizmijenjene = sinkroniziraj_zone()
        st.session_state.last_sync = datetime.now().strftime("%d.%m.%Y %H:%M")

        if nove > 0 or azurirane > 0:
            st.success(
                f"✅ Sinkronizacija završena!\n- Nove zone: {nove}\n- Ažurirane: {azurirane}"
            )
            st.rerun()
        else:
            st.info("ℹ️ Nema promjena.")

with tab3:
    st.subheader("🧪 Testiranje komunikacije s centralom")

    if AXPRO_AVAILABLE:
        # Prikaz konfiguracije
        with st.expander("ℹ️ Konfiguracija centrale"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Host:** {HOST}")
            with col2:
                st.write(f"**Username:** {USERNAME}")
            with col3:
                st.write(f"**Password:** {'*' * len(PASSWORD)}")

    # Test konekcije i prikaz zona s detaljima (identično kao u testnoj stranici)
    if st.button("🔌 Spoji se i prikaži zone", disabled=not AXPRO_AVAILABLE):
        zone_list = get_zone_status_detailed()
        if zone_list:
            st.success(f"✅ Učitano {len(zone_list)} zona.")

            # Prikaži podatke u tablici
            df = pd.DataFrame(zone_list)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Provjeri aktivne alarme
            active = df[df["alarm"] == True]
            if not active.empty:
                st.warning(f"‼️ Aktivni alarmi ({len(active)}):")
                for _, z in active.iterrows():
                    st.markdown(f"- **{z['name']}** (ID: {z['id']})")
            else:
                st.info("✅ Nema aktivnih alarma.")

    # Reset alarma (identično kao u testnoj stranici)
    st.markdown("---")
    st.subheader("🧹 Resetiraj sve alarme na centrali")

    if st.button("🧯 Resetiraj alarme", disabled=not AXPRO_AVAILABLE):
        success, response = reset_alarme_na_centrali()
        if success:
            st.success("✅ Alarmi uspješno resetirani!")
            st.code(response, language="text")
        else:
            st.error(f"❌ Greška pri resetiranju: {response}")

# Log sekcija
st.markdown("---")
st.subheader("📜 Log aktivnosti")

# Kontrole za log
col_log1, col_log2 = st.columns([3, 1])
with col_log2:
    if st.button("🧹 Očisti log", use_container_width=True):
        st.session_state.sync_log = []
        st.rerun()

if st.session_state.sync_log:
    # Prikaži zadnjih 15 log poruka
    recent_logs = st.session_state.sync_log[-15:]

    for log_entry in reversed(recent_logs):
        if log_entry["type"] == "error":
            st.error(f"[{log_entry['time']}] {log_entry['message']}")
        elif log_entry["type"] == "warning":
            st.warning(f"[{log_entry['time']}] {log_entry['message']}")
        elif log_entry["type"] == "success":
            st.success(f"[{log_entry['time']}] {log_entry['message']}")
        else:
            st.info(f"[{log_entry['time']}] {log_entry['message']}")
else:
    st.info("ℹ️ Nema log poruka.")

# Footer
st.markdown("---")
st.markdown(
    "<sub>© Robert M., 2025 – Admin Panel za Alarmni Sustav</sub>",
    unsafe_allow_html=True,
)
