import streamlit as st
import pandas as pd
import sqlite3
from admin import DB_PATH

# Page configuration
st.set_page_config(page_title="Korisnici", page_icon="👥", layout="wide")

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

st.subheader("👥 Upravljanje Korisnicima")

# Database functions
def get_korisnici_data():
    """Dohvati korisnike s dodijeljenim narukvicama"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(
                """
                SELECT k.id AS korisnik_id, k.ime, k.soba,
                       z.id AS zona_id, z.naziv AS zona_naziv
                FROM korisnici k
                LEFT JOIN zone z ON k.id = z.korisnik_id
                ORDER BY k.ime
            """,
                conn,
            )
    except Exception as e:
        st.error(f"Greška pri dohvaćanju korisnika: {e}")
        return pd.DataFrame()


def get_slobodne_narukvice():
    """Dohvati narukvice koje nisu dodijeljene nijednom korisniku"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(
                """
                SELECT z.id, z.naziv 
                FROM zone z 
                WHERE z.korisnik_id IS NULL
                ORDER BY z.id
            """,
                conn,
            )
    except Exception as e:
        st.error(f"Greška pri dohvaćanju slobodnih narukvica: {e}")
        return pd.DataFrame()


def kreiraj_korisnika(ime, soba):
    """Kreiraj novog korisnika"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "INSERT INTO korisnici (ime, soba) VALUES (?, ?)", (ime, soba)
            )
            conn.commit()
            return True, cur.lastrowid
    except Exception as e:
        st.error(f"Greška pri kreiranju korisnika: {e}")
        return False, None


def update_korisnik(korisnik_id, ime, soba):
    """Ažuriraj korisnika"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE korisnici SET ime = ?, soba = ? WHERE id = ?",
                (ime, soba, korisnik_id),
            )
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri ažuriranju korisnika: {e}")
        return False


def dodijeli_narukvicu_korisniku(korisnik_id, zona_id):
    """Dodijeli narukvicu korisniku (jedan korisnik = jedna narukvica)"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Provjeri ima li korisnik već narukvicu
            cur = conn.execute(
                "SELECT COUNT(*) FROM zone WHERE korisnik_id = ?", (korisnik_id,)
            )
            if cur.fetchone()[0] > 0:
                st.error("❌ Korisnik već ima dodijeljenu narukvicu!")
                return False

            # Dodijeli narukvicu
            conn.execute(
                "UPDATE zone SET korisnik_id = ? WHERE id = ?", (korisnik_id, zona_id)
            )
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri dodjeli narukvice: {e}")
        return False


def otkvaci_narukvicu_od_korisnika(zona_id):
    """Otkvači narukvicu od korisnika (korisnik ostaje u tablici)"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE zone SET korisnik_id = NULL WHERE id = ?", (zona_id,))
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri otkvačivanju narukvice: {e}")
        return False


def obrisi_korisnika(korisnik_id):
    """Obriši korisnika i otkvači sve njegove narukvice"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Prvo otkvači sve narukvice korisnika
            conn.execute(
                "UPDATE zone SET korisnik_id = NULL WHERE korisnik_id = ?",
                (korisnik_id,),
            )
            # Zatim obriši korisnika
            conn.execute("DELETE FROM korisnici WHERE id = ?", (korisnik_id,))
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri brisanju korisnika: {e}")
        return False


# Main content
korisnici_df = get_korisnici_data()
slobodne_narukvice_df = get_slobodne_narukvice()

if korisnici_df.empty:
    st.warning("⚠️ Nema korisnika u sustavu.")

    # Opcija za kreiranje prvog korisnika
    st.subheader("➕ Kreiraj prvog korisnika")
    with st.form("kreiraj_prvi_korisnik"):
        col1, col2 = st.columns(2)
        with col1:
            ime = st.text_input("Ime korisnika:")
        with col2:
            soba = st.text_input("Soba:")

        if st.form_submit_button("➕ Kreiraj korisnika", width="stretch"):
            if not ime.strip():
                st.error("❌ Ime je obavezno!")
            else:
                success, korisnik_id = kreiraj_korisnika(
                    ime.strip(), soba.strip() or None
                )
                if success:
                    st.success(f"✅ Korisnik '{ime}' kreiran!")
                    st.rerun()
else:
    # Statistike korisnika
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "👥 Ukupno korisnika", len(korisnici_df.drop_duplicates("korisnik_id"))
        )
    with col2:
        s_narukvicama = len(
            korisnici_df[korisnici_df["zona_id"].notna()].drop_duplicates("korisnik_id")
        )
        st.metric("🟢 S narukvicama", s_narukvicama)
    with col3:
        bez_narukvica = len(korisnici_df[korisnici_df["zona_id"].isna()])
        st.metric("⚪ Bez narukvica", bez_narukvica)

    st.markdown("---")

    # Filter korisnika
    filter_option = st.selectbox(
        "🔍 Filtriraj korisnike:",
        ["Svi korisnici", "S narukvicama", "Bez narukvica"],
    )

    # Pripremi podatke - jedan korisnik = jedan red
    korisnici_summary = korisnici_df.drop_duplicates("korisnik_id")

    if filter_option == "S narukvicama":
        korisnici_summary = korisnici_summary[korisnici_summary["zona_id"].notna()]
    elif filter_option == "Bez narukvica":
        korisnici_summary = korisnici_summary[korisnici_summary["zona_id"].isna()]

    if korisnici_summary.empty:
        st.info(f"ℹ️ Nema korisnika u kategoriji '{filter_option}'.")
    else:
        st.subheader(f"👥 Korisnici ({len(korisnici_summary)})")

        # Kreiranje novog korisnika
        with st.expander("➕ Kreiraj novog korisnika"):
            with st.form("kreiraj_novi_korisnik"):
                col1, col2 = st.columns(2)
                with col1:
                    novo_ime = st.text_input("Ime korisnika:")
                with col2:
                    nova_soba = st.text_input("Soba:")

                if st.form_submit_button("➕ Kreiraj korisnika", width="stretch"):
                    if not novo_ime.strip():
                        st.error("❌ Ime je obavezno!")
                    else:
                        success, korisnik_id = kreiraj_korisnika(
                            novo_ime.strip(), nova_soba.strip() or None
                        )
                        if success:
                            st.success(f"✅ Korisnik '{novo_ime}' kreiran!")
                            st.rerun()
        st.markdown("---")
        # Prikaz korisnika
        for _, row in korisnici_summary.iterrows():
            korisnik_id = row["korisnik_id"]
            ime = row["ime"]
            soba = row["soba"]
            zona_id = row["zona_id"]
            zona_naziv = row["zona_naziv"]

            # Status i prikaz informacija
            has_narukvica = pd.notna(zona_id)
            korisnik_status = "🟢" if has_narukvica else "⚪"
            narukvice_info = zona_naziv if has_narukvica else "Nema narukvicu"
            soba_info = f" (Soba: {soba})" if soba else ""

            with st.expander(f"{korisnik_status} {ime}{soba_info} → {narukvice_info}"):
                # Osnovne informacije
                st.markdown(f"**Korisnik ID:** {korisnik_id}")
                st.markdown(f"**Ime:** {ime}")
                if soba:
                    st.markdown(f"**Soba:** {soba}")

                # Prikaz narukvice s opcijom otkvačivanja
                if has_narukvica:
                    st.markdown("**Dodijeljena narukvica:**")
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"• {zona_naziv}")
                    with col2:
                        if st.button(
                            "🔓 Otkvači",
                            key=f"otkvaci_{korisnik_id}_{zona_id}",
                            help="Otkvači narukvicu od korisnika",
                        ):
                            if otkvaci_narukvicu_od_korisnika(zona_id):
                                st.success("✅ Narukvica otkvačena!")
                                st.rerun()

                # Akcije za korisnika
                akcija = st.radio(
                    "Odaberi akciju:",
                    ["Editiraj korisnika", "Dodijeli narukvicu", "Obriši korisnika"],
                    key=f"akcija_korisnik_{korisnik_id}",
                )

                if akcija == "Editiraj korisnika":
                    with st.form(f"edit_korisnik_{korisnik_id}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            novo_ime = st.text_input(
                                "Ime:", value=ime, key=f"edit_ime_k_{korisnik_id}"
                            )
                        with col2:
                            nova_soba = st.text_input(
                                "Soba:",
                                value=soba or "",
                                key=f"edit_soba_k_{korisnik_id}",
                            )

                        if st.form_submit_button("💾 Spremi promjene", width="stretch"):
                            if update_korisnik(
                                korisnik_id, novo_ime.strip(), nova_soba.strip() or None
                            ):
                                st.success("✅ Korisnik ažuriran!")
                                st.rerun()

                elif akcija == "Dodijeli narukvicu":
                    if has_narukvica:
                        st.info(
                            "ℹ️ Korisnik već ima dodijeljenu narukvicu. Otkvačite postojeću prije dodjele nove."
                        )
                    elif len(slobodne_narukvice_df) > 0:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            selected_narukvica = st.selectbox(
                                "Odaberi slobodnu narukvicu:",
                                options=slobodne_narukvice_df["id"].tolist(),
                                format_func=lambda x: slobodne_narukvice_df[
                                    slobodne_narukvice_df["id"] == x
                                ]["naziv"].iloc[0],
                                key=f"select_narukvica_{korisnik_id}",
                            )
                        with col2:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button(
                                "🔗 Dodijeli",
                                key=f"dodijeli_{korisnik_id}",
                                width="stretch",
                            ):
                                if dodijeli_narukvicu_korisniku(
                                    korisnik_id, selected_narukvica
                                ):
                                    st.success("✅ Narukvica dodijeljena korisniku!")
                                    st.rerun()
                    else:
                        st.info("ℹ️ Nema slobodnih narukvica za dodjelu.")

                elif akcija == "Obriši korisnika":
                    if has_narukvica:
                        st.warning(
                            "⚠️ Korisnik ima dodijeljene narukvice koje će biti otkvačene!"
                        )
                    st.error("❌ Korisnik će biti potpuno obrisan iz sustava!")
                    if st.button(
                        f"🗑️ Obriši korisnika",
                        key=f"delete_korisnik_{korisnik_id}",
                        type="secondary",
                        width="stretch",
                    ):
                        if obrisi_korisnika(korisnik_id):
                            st.success("✅ Korisnik obrisan!")
                            st.rerun()

st.markdown("---")
st.markdown(
    "<sub>© Robert M., 2025 – Admin Panel za Alarmni Sustav</sub>",
    unsafe_allow_html=True,
)
