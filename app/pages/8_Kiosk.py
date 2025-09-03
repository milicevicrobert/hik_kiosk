import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from static.alarm_base64 import base64_mp3

DB_PATH = "data/alarmni_sustav.db"

# ------------------ Konfiguracija ------------------
st.set_page_config(
    page_title="Alarm Kiosk", 
    layout="wide",
    menu_items={
        'About': None,
        'Get help': None,
        'Report a bug': None
    }
)

# ------------------ CSS ------------------
st.markdown("""
    <style>
        .main .block-container { padding-top: 0rem !important; }
        .title-container { margin-top: 0 !important; padding-top: 0 !important; padding-bottom: 0rem; margin-bottom: 0rem; }
        .title-container h1 { font-size: 1.8rem !important; text-align: center !important; margin: 0.2rem 0 !important; padding: 0 !important; }
        header[data-testid="stHeader"] { display: none !important; }
        #MainMenu { visibility: hidden; }
        div[data-testid="stExpander"] details summary p { font-size: 1.5rem !important; font-weight: bold !important; }
        div[data-testid="stExpander"] div[role="button"] p { font-size: 1.5rem !important; }
        .stTextInput input { font-size: 1.5rem !important; height: 3.5rem !important; }
        button { font-size: 1.5rem !important; padding: 0.75rem 1.5rem !important; }
        .stMarkdown { font-size: 1.5rem !important; }
        .stAlert { font-size: 1.5rem !important; }
        footer { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

# ------------------ Automatsko osvježavanje ------------------
st_autorefresh(interval=2000, key="auto_refresh")

# ------------------ Pomoćne funkcije ------------------
def get_connection():
    return sqlite3.connect(DB_PATH)

def validan_pin(pin: str, duljina: int = 4) -> bool:
    return pin.isdigit() and len(pin) == duljina

def set_comm_flag(key, value=1):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO comm (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        conn.commit()

def get_aktivni_alarms():
    with get_connection() as conn:
        return pd.read_sql_query("""
            SELECT id, zone_id, zone_name, vrijeme, korisnik, soba
            FROM alarms
            WHERE potvrda = 0
            ORDER BY vrijeme DESC
        """, conn)

def validiraj_osoblje(pin):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, ime FROM osoblje WHERE sifra = ? AND aktivna = 1", (pin,))
        return cur.fetchone()

def potvrdi_alarm(alarm_id, osoblje_ime):
    with get_connection() as conn:
        conn.execute("""
            UPDATE alarms
            SET potvrda = 1,
                osoblje = ?,
                vrijemePotvrde = ?
            WHERE id = ?
        """, (osoblje_ime, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), alarm_id))
        conn.commit()

# ------------------ Stanje aplikacije ------------------
alarms_df = get_aktivni_alarms()
trenutni_alarm_ids = set(alarms_df["id"].tolist())

if "sound_muted" not in st.session_state:
    st.session_state["sound_muted"] = False

if "posljednji_alarm_ids" not in st.session_state:
    st.session_state["posljednji_alarm_ids"] = set()

if trenutni_alarm_ids != st.session_state["posljednji_alarm_ids"]:
    st.session_state["sound_muted"] = False
    st.session_state["posljednji_alarm_ids"] = trenutni_alarm_ids

# ------------------ Naslov i gumb za zvuk ------------------
col1, col2 = st.columns([4, 2])
with col1:
    st.markdown("""
        <div class="title-container">
            <h1>🚨 AKTIVNI ALARMI</h1>
        </div>
    """, unsafe_allow_html=True)
with col2:
    if st.session_state["sound_muted"]:
        if st.button("🔊 Uključi zvuk"):
            st.session_state["sound_muted"] = False
    else:
        if st.button("🔇 Isključi zvuk"):
            st.session_state["sound_muted"] = True

# ------------------ Obavijest ------------------
if "obavijest" in st.session_state:
    st.success(st.session_state["obavijest"], icon="✅")
    del st.session_state["obavijest"]

if "zadnji_potvrdio" in st.session_state:
    st.info(
        f"🆔 Posljednji alarm je potvrdio: **{st.session_state['zadnji_potvrdio']}** "
        f"u {st.session_state['zadnji_potvrdio_vrijeme']}"
    )
    del st.session_state["zadnji_potvrdio"]
    del st.session_state["zadnji_potvrdio_vrijeme"]

# ------------------ Zvuk alarma ------------------
if not alarms_df.empty and not st.session_state["sound_muted"]:
    st.markdown(f"""
        <audio autoplay loop>
            <source src="data:audio/mpeg;base64,{base64_mp3}" type="audio/mpeg">
        </audio>
    """, unsafe_allow_html=True)

# ------------------ Prikaz alarma ------------------
if alarms_df.empty:
    st.info("✅ Trenutno nema aktivnih alarma.", icon="ℹ️")
else:
    for _, row in alarms_df.iterrows():
        try:
            samo_vrijeme = datetime.strptime(row['vrijeme'], "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
        except Exception:
            samo_vrijeme = row['vrijeme']

        with st.expander(
           f"🚨 {row['zone_name'].upper()} (ID: {row['zone_id']}) • 👤 {row['korisnik'] or 'NEPOZNAT'} • 🛏️ SOBA: {row.get('soba', 'N/A')} • 🕒 {samo_vrijeme}",
            expanded=False
        ):
            with st.form(f"forma_potvrda_{row['id']}"):
                cols = st.columns([3, 1])
                with cols[0]:
                    pin = st.number_input(
                        "**PIN (4 znamenke):**",
                        min_value=0,
                        max_value=9999,
                        step=1,
                        format="%d",
                        key=f"pin_{row['id']}"
                    )
                    pin = str(int(pin)).zfill(4)

                with cols[1]:
                    st.write("")
                    potvrdi = st.form_submit_button("POTVRDI", type="primary")

                if potvrdi:
                    if not validan_pin(pin):
                        st.error("⚠️ Unesite ispravan PIN (4 znamenke!)", icon="⚠️")
                    else:
                        osoblje = validiraj_osoblje(pin)
                        if osoblje:
                            potvrdi_alarm(row["id"], osoblje[1])
                            set_comm_flag("resetAlarm", 1)
                            st.session_state["obavijest"] = f"✔️ Alarm potvrđen od: {osoblje[1]}"
                            st.session_state["zadnji_potvrdio"] = osoblje[1]
                            st.session_state["zadnji_potvrdio_vrijeme"] = datetime.now().strftime("%H:%M:%S")
                            st.rerun()
                        else:
                            st.error("❌ Neispravan PIN ili neaktivno osoblje!", icon="❌")


st.markdown('<hr style="margin-top:2em; margin-bottom:0.5em;">', unsafe_allow_html=True)
st.markdown('<div style="text-align:center; color:gray; font-size:0.95em;">© Robert Miličević</div>', unsafe_allow_html=True)
