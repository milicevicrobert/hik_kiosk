import streamlit as st
import sqlite3
import pandas as pd
from admin_config import DB_PATH
# ------------------ Konfiguracija stranice ------------------
st.set_page_config(page_title="Zone", layout="centered")
st.markdown("""
    <style>
        div[data-testid="stToolbar"] button {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)
st.title("📡 Upravljanje zonama")
st.caption("Svaka zona može imati jednog korisnika. Svaki korisnik može biti dodijeljen samo jednoj zoni.")

# ------------------ Funkcije ------------------

def get_zone_data():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("""
            SELECT z.id AS zona_id, z.naziv AS zona_naziv,
                   k.id AS korisnik_id, k.ime, k.soba
            FROM zone z
            LEFT JOIN korisnici k ON z.korisnik_id = k.id
            ORDER BY z.id
        """, conn)

def get_svi_korisnici():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT id, ime, soba FROM korisnici", conn)

def povezi_korisnika_na_zonu(zona_id, korisnik_id):
    with sqlite3.connect(DB_PATH) as conn:
        # Oslobodi korisnika iz drugih zona (ako postoji)
        if korisnik_id is not None:
            conn.execute("UPDATE zone SET korisnik_id = NULL WHERE korisnik_id = ?", (korisnik_id,))
        # Postavi korisnika (ili NULL)
        conn.execute("UPDATE zone SET korisnik_id = ? WHERE id = ?", (korisnik_id, zona_id))
        conn.commit()

# ------------------ Prikaz ------------------

zone_df = get_zone_data()
korisnici_df = get_svi_korisnici()

# Izračunaj koji su korisnici već povezani s nekom zonom
zauzeti_korisnici = zone_df["korisnik_id"].dropna().unique().tolist()

if zone_df.empty:
    st.warning("⚠️ Nema definiranih zona u sustavu.")
else:
    for _, row in zone_df.iterrows():
        # ID trenutno dodijeljenog korisnika (može biti None)
        trenutno_id = row["korisnik_id"]

        # Priprema prikaza korisnika
        dostupni_korisnici = korisnici_df[~korisnici_df["id"].isin(zauzeti_korisnici)]
        # Ako zona već ima korisnika, dodaj ga natrag u listu
        if trenutno_id is not None:
            dodatni = korisnici_df[korisnici_df["id"] == trenutno_id]
            dostupni_korisnici = pd.concat([dostupni_korisnici, dodatni]).drop_duplicates("id")

        dostupni_korisnici["prikaz"] = dostupni_korisnici.apply(
            lambda r: f"{r['ime']} (Soba {r['soba']})" if pd.notna(r["soba"]) else r["ime"], axis=1
        )

        # Mapa prikaza
        korisnik_map = {ime: id_ for ime, id_ in zip(dostupni_korisnici["prikaz"], dostupni_korisnici["id"])}
        prikazi = ["None"] + list(korisnik_map.keys())
        korisnik_map["None"] = None

        # Prikaži ime trenutnog korisnika (ili "None")
        ime_korisnika = next((k for k, v in korisnik_map.items() if v == trenutno_id), "None")

        with st.expander(f"📍 ID: {row['zona_id']} – {row['zona_naziv']} – 👤 {ime_korisnika}"):
            selected = st.selectbox(
                "Odaberi korisnika:",
                options=prikazi,
                index=prikazi.index(ime_korisnika) if ime_korisnika in prikazi else 0,
                key=f"select_{row['zona_id']}"
            )

            if st.button("💾 Spremi", key=f"spremi_{row['zona_id']}"):
                korisnik_id = korisnik_map[selected]
                povezi_korisnika_na_zonu(row["zona_id"], korisnik_id)
                st.success("✔️ Zona ažurirana.")
                st.rerun()

st.markdown('<hr style="margin-top:2em; margin-bottom:0.5em;">', unsafe_allow_html=True)
st.markdown('<div style="text-align:right; color:gray; font-size:0.95em;">&copy; RM 2025</div>', unsafe_allow_html=True)
