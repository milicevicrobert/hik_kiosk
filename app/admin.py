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
    "data/alarmni_sustav.db",
    "static"]

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
st.markdown("<span style='font-size:1.5em;'>🔍 <b>System Health</b></span>", unsafe_allow_html=True)

st.markdown("---")

st.markdown(f"""
**📁 BASE_DIR:**  <code>{BASE_DIR}</code>

**🗄️ DB_PATH:**  <code>{DB_PATH}</code>
""", unsafe_allow_html=True)

st.markdown("---")

rezultati = provjeri_postojanje(MAPA, STAVKE)
cols = st.columns(3)  # 3 kolone

for idx, (ime, tip, postoji) in enumerate(rezultati):
    col = cols[idx % 3]
    ikona = "✅" if postoji else "❌"
    tip_ikona = "📁" if tip == "direktorij" else ("📄" if tip == "datoteka" else "❓")
    boja = "grey" if postoji else "red"
    col.markdown(
        f"<span style='font-size:1em; color:{boja};'>{ikona} {tip_ikona} <b>{ime}</b></span><br>",
        
        unsafe_allow_html=True,
    )
st.markdown("---")
# Footer
st.markdown(
    "<sub>© RM., 2025 – Admin Panel za Alarmni Sustav</sub>",
    unsafe_allow_html=True,
)
