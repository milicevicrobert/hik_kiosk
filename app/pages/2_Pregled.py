import streamlit as st
import sqlite3
import pandas as pd
import os
from admin_config import DB_PATH

baza_path = DB_PATH

st.set_page_config("📋 Pregled zapisa", layout="wide")
st.markdown("""
    <style>
        div[data-testid="stToolbar"] button {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📋 Pregled svih podataka iz baze")

# Dohvati sve nazive tablica iz baze
def ucitaj_tablice(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [t[0] for t in cursor.fetchall()]

# Dohvati sve podatke iz zadane tablice
def ucitaj_podatke(conn, tablica):
    return pd.read_sql_query(f"SELECT * FROM {tablica}", conn)

# Ako baza postoji, prikaži sve dostupno
if os.path.isfile(baza_path):
    with sqlite3.connect(baza_path) as conn:
        tablice = ucitaj_tablice(conn)
        if tablice:
            odabrana_tablica = st.selectbox("📂 Odaberi tablicu za prikaz:", tablice)
            df = ucitaj_podatke(conn, odabrana_tablica)

            st.markdown(f"### 📄 Podaci iz tablice `{odabrana_tablica}`")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("🔎 Baza je prazna (nema tablica).")
else:
    st.warning("⚠️ Baza ne postoji na toj putanji.")

st.markdown('<hr style="margin-top:2em; margin-bottom:0.5em;">', unsafe_allow_html=True)
st.markdown('<div style="text-align:right; color:gray; font-size:0.95em;">&copy; RM 2025</div>', unsafe_allow_html=True)
