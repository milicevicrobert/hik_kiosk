import streamlit as st
import sqlite3
import pandas as pd
from admin import DB_PATH

st.set_page_config(page_title="Osoblje", layout="centered")
st.markdown("""
    <style>
        div[data-testid="stToolbar"] button {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🧑‍⚕️ Upravljanje osobljem")
st.caption("Dodavanje, uređivanje i brisanje djelatnika koji potvrđuju alarme (PIN obavezan, 5 znamenki).")

# -------------------- Funkcija za dohvat osoblja --------------------
def get_osoblje():
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM osoblje", conn)
    return df

# -------------------- Dodavanje novog osoblja --------------------
with st.expander("➕ Dodaj novo osoblje"):
    with st.form("unos_forma"):
        ime = st.text_input("Ime i prezime").strip()
        sifra = st.text_input("PIN (4 znamenke)", type="password", max_chars=4)
        aktivna = st.checkbox("Aktivna", value=True)
        submit = st.form_submit_button("💾 Spremi")

        if submit:
            if not ime or not sifra.isdigit() or len(sifra) != 4:
                st.error("Unesi ispravno ime i PIN (točno 4 znamenke).")
            else:
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT * FROM osoblje WHERE sifra = ?", (sifra,))
                        if cur.fetchone():
                            st.error("⚠️ PIN već postoji – unesi jedinstveni PIN.")
                        else:
                            cur.execute("""
                                INSERT INTO osoblje (ime, sifra, aktivna)
                                VALUES (?, ?, ?)
                            """, (ime, sifra, int(aktivna)))
                            conn.commit()
                            st.success(f"✔️ Osoba '{ime}' dodana.")
                            st.rerun()
                except Exception as e:
                    st.error(f"Greška: {e}")

# -------------------- Prikaz i uređivanje osoblja --------------------
st.markdown("---")
st.subheader("📋 Trenutni popis osoblja")

df = get_osoblje()
if df.empty:
    st.info("Nema unesenih članova osoblja.")
else:
    for _, row in df.iterrows():
        aktivna_oznaka = "✅" if row["aktivna"] else "❌"
        naslov = f"🧑‍⚕️ {row['ime']} – PIN: `{row['sifra']}` – Aktivna: {aktivna_oznaka}"

        with st.expander(naslov):
            with st.form(f"uredi_forma_{row['id']}"):
                novo_ime = st.text_input("Ime i prezime", value=row["ime"])
                nova_sifra = st.text_input("PIN (4 znamenke)", value=row["sifra"], max_chars=5)
                nova_aktivna = st.checkbox("Aktivna", value=bool(row["aktivna"]))
                col1, col2 = st.columns(2)
                potvrdi = col1.form_submit_button("💾 Spremi promjene")

                if potvrdi:
                    if not novo_ime or not nova_sifra.isdigit() or len(nova_sifra) != 4:
                        st.error("Unesi ispravno ime i PIN (točno 4 znamenke).")
                    else:
                        try:
                            with sqlite3.connect(DB_PATH) as conn:
                                cur = conn.cursor()
                                # Provjera postoji li drugi korisnik s istim PIN-om
                                cur.execute("SELECT id FROM osoblje WHERE sifra = ? AND id != ?", (nova_sifra, row["id"]))
                                if cur.fetchone():
                                    st.error("⚠️ Taj PIN već koristi druga osoba.")
                                else:
                                    cur.execute("""
                                        UPDATE osoblje
                                        SET ime = ?, sifra = ?, aktivna = ?
                                        WHERE id = ?
                                    """, (novo_ime, nova_sifra, int(nova_aktivna), row["id"]))
                                    conn.commit()
                                    st.success("✔️ Promjene su spremljene.")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Greška: {e}")

st.markdown('<hr style="margin-top:2em; margin-bottom:0.5em;">', unsafe_allow_html=True)
st.markdown('<div style="text-align:right; color:gray; font-size:0.95em;">&copy; RM 2025</div>', unsafe_allow_html=True)
