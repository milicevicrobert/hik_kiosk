import streamlit as st
import sqlite3
import pandas as pd
from admin_config import DB_PATH

st.set_page_config(page_title="Korisnici", layout="centered")
st.markdown("""
    <style>
        div[data-testid="stToolbar"] button {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)
st.title("👤 Upravljanje korisnicima")
st.caption("Dodavanje i upravljanje korisnicima (bez povezivanja sa zonama).")

# ---------------- Funkcije ----------------

def get_korisnici():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM korisnici ORDER BY id", conn)

def dodaj_korisnika(ime, soba):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO korisnici (ime, soba) VALUES (?, ?)
        """, (ime, soba))
        conn.commit()

def update_korisnik(k_id, ime, soba):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            UPDATE korisnici SET ime = ?, soba = ? WHERE id = ?
        """, (ime, soba, k_id))
        conn.commit()

def obrisi_korisnika(k_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM korisnici WHERE id = ?", (k_id,))
        conn.commit()

# ---------------- Dodavanje ----------------

with st.expander("➕ Dodaj novog korisnika"):
    with st.form("unos_korisnika"):
        ime = st.text_input("Ime", key="novo_ime")
        soba = st.text_input("Soba", key="nova_soba")
        submit = st.form_submit_button("📥 Spremi korisnika")

        if submit:
            if not ime.strip():
                st.error("❌ Ime je obavezno.")
            else:
                try:
                    dodaj_korisnika(ime.strip(), soba.strip())
                    st.success(f"Korisnik '{ime}' dodan.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Greška pri dodavanju: {e}")

# ---------------- Prikaz i uređivanje ----------------

st.markdown("---")
st.subheader("📋 Trenutni korisnici")

korisnici_df = get_korisnici()

if korisnici_df.empty:
    st.info("ℹ️ Nema unesenih korisnika.")
else:
    for _, row in korisnici_df.iterrows():
        prikaz = f"{row['ime']} – Soba {row['soba']}" if pd.notna(row["soba"]) else row["ime"]
        with st.expander(prikaz):
            with st.form(f"forma_{row['id']}"):
                novo_ime = st.text_input("Ime", value=row["ime"], key=f"ime_{row['id']}")
                nova_soba = st.text_input("Soba", value=row["soba"], key=f"soba_{row['id']}")
                col1, col2 = st.columns(2)
                with col1:
                    spremi = st.form_submit_button("📥 Spremi")
                with col2:
                    obrisi = st.form_submit_button("🗑️ Obriši")

                if spremi:
                    update_korisnik(row["id"], novo_ime.strip(), nova_soba.strip())
                    st.success("✔️ Podaci ažurirani.")
                    st.rerun()
                if obrisi:
                    obrisi_korisnika(row["id"])
                    st.warning("🗑️ Korisnik obrisan.")
                    st.rerun()

st.markdown('<hr style="margin-top:2em; margin-bottom:0.5em;">', unsafe_allow_html=True)
st.markdown('<div style="text-align:right; color:gray; font-size:0.95em;">&copy; RM 2025</div>', unsafe_allow_html=True)
