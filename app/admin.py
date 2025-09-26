import streamlit as st
import os
import sqlite3
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR,"data", "alarmni_sustav.db")

# PRIMJER KORIŠTENJA:
MAPA = BASE_DIR 
STAVKE = [
    "admin.py",
    "kiosk.py", 
    "scan.py", 
    "module",
    "data",
    "pages",
    "module/axpro_auth.py", 
    "data/alarmni_sustav.db",]

# -------------- Help functions --------------

def provjeri_postojanje(putanja, stavke):
    """Provjeri postoji li svaka stavka (file ili dir) u zadanoj mapi."""
    rezultati = []
    for ime in stavke:
        puni_put = os.path.join(putanja, ime)
        if os.path.isdir(puni_put):
            rezultati.append((ime, "direktorij", True))
        elif os.path.isfile(puni_put):
            rezultati.append((ime, "datoteka", True))
        else:
            rezultati.append((ime, "ne postoji", False))
    return rezultati


# Streamlit app configuration
st.set_page_config(
    page_title="Administracija sustava narukvica",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

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


# System health monitoring
st.subheader("🔍 System Health")
st.markdown("---")
rezultati = provjeri_postojanje(MAPA, STAVKE)

cols = st.columns(3)  # 3 kolone

for idx, (ime, tip, postoji) in enumerate(rezultati):
    col = cols[idx % 3]
    col.write(f"{ime}: {'✅' if postoji else '❌'} ({tip})")

st.markdown("---")
st.write(f"BASE_DIR: {BASE_DIR}")
st.write(f"DB_PATH: {DB_PATH}")

st.markdown(
    "<sub>© Robert M., 2025 – Admin Panel za Alarmni Sustav</sub>",
    unsafe_allow_html=True,
)
