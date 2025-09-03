import streamlit as st
import sqlite3
import pandas as pd
from admin_config import DB_PATH
from datetime import timedelta, date

st.set_page_config(
    page_title="Alarmni",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
    
)

st.markdown("""
    <style>
        div[data-testid="stToolbar"] button {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)
st.title("🚨 Pregled alarma")
st.caption("Pretražujte i filtrirajte alarme po korisniku, osoblju ili datumu.")

# --- Filteri iznad tablice ---
with st.expander("🔎 Filteri", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        korisnik = st.text_input("Korisnik")
    with col2:
        osoblje = st.text_input("Osoblje")
    with col3:
        datum_od = st.date_input("Datum od", value=date.today())
    with col4:
        datum_do = st.date_input("Datum do", value=date.today())

if datum_od and datum_do:
    datum_od_str = datum_od.strftime("%Y-%m-%d")
    datum_do_str = datum_do.strftime("%Y-%m-%d")
else:
    datum_od_str = None
    datum_do_str = None

st.caption(f"Prikaz od {datum_od_str or '-'} do {datum_do_str or '-'}")

# --- Funkcija za dohvat alarma ---
def get_alarms(korisnik=None, osoblje=None, datum_od=None, datum_do=None):
    query = "SELECT * FROM alarms WHERE 1=1"
    params = []
    if korisnik:
        query += " AND korisnik LIKE ?"
        params.append(f"%{korisnik}%")
    if osoblje:
        query += " AND osoblje LIKE ?"
        params.append(f"%{osoblje}%")
    if datum_od and datum_do:
        query += " AND DATE(vrijeme) BETWEEN ? AND ?"
        params.extend([datum_od, datum_do])
    query += " ORDER BY vrijeme DESC"
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn, params=params)

# --- Prikaz rezultata ---
alarms_df = get_alarms(korisnik, osoblje, datum_od_str, datum_do_str)

if alarms_df.empty:
    st.info("Nema alarma za zadane filtere.")
else:
    st.dataframe(alarms_df, use_container_width=True)
    st.markdown(f"**Broj prikazanih alarma:** {len(alarms_df)}")

# --- Brisanje starih alarma ---
with st.expander("🗑️ Brisanje starih alarma", expanded=False):
    datum_brisi = st.date_input("Obriši sve alarme starije od:", value=date.today())
    datum_brisi_str = datum_brisi.strftime("%Y-%m-%d")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM alarms WHERE DATE(vrijeme) < ?", (datum_brisi_str,))
        broj_za_brisanje = cur.fetchone()[0]
    st.info(f"Broj alarma za brisanje: {broj_za_brisanje}")
    if broj_za_brisanje > 0 and st.button("Obriši stare alarme"):
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM alarms WHERE DATE(vrijeme) < ?", (datum_brisi_str,))
            conn.commit()
        st.success(f"Obrisano {broj_za_brisanje} alarma.")

st.markdown('<hr style="margin-top:2em; margin-bottom:0.5em;">', unsafe_allow_html=True)
st.markdown('<div style="text-align:right; color:gray; font-size:0.95em;">&copy; RM 2025</div>', unsafe_allow_html=True)
