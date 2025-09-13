import streamlit as st
import pandas as pd
import sqlite3
from admin_config import DB_PATH

# Page configuration
st.set_page_config(
    page_title="Narukvice", 
    page_icon="👥", 
    layout="wide"
)

# Hide Streamlit menu
st.markdown("""
    <style>
        div[data-testid="stToolbar"] button {
            display: none !important;
        }
        .main > div { padding-top: 2rem; }
    </style>
""", unsafe_allow_html=True)

st.title("📿 Upravljanje Narukvicama")
st.caption("Dodjeljivanje i upravljanje narukvicama i korisnicima")

# Database functions
def get_korisnici():
    """Dohvati sve korisnike"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("SELECT * FROM korisnici ORDER BY id", conn)
    except Exception as e:
        st.error(f"Greška pri dohvaćanju korisnika: {e}")
        return pd.DataFrame()

def dodaj_korisnika(ime, soba):
    """Dodaj novog korisnika"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO korisnici (ime, soba) VALUES (?, ?)", (ime, soba))
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri dodavanju korisnika: {e}")
        return False

def update_korisnik(k_id, ime, soba):
    """Ažuriraj korisnika"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE korisnici SET ime = ?, soba = ? WHERE id = ?", (ime, soba, k_id))
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri ažuriranju korisnika: {e}")
        return False

def obrisi_korisnika(k_id):
    """Obriši korisnika i ukloni ga iz zona"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Prvo ukloni korisnika iz svih zona
            conn.execute("UPDATE narukvice SET korisnik_id = NULL WHERE korisnik_id = ?", (k_id,))
            # Zatim obriši korisnika
            conn.execute("DELETE FROM korisnici WHERE id = ?", (k_id,))
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri brisanju korisnika: {e}")
        return False

def get_zone_data():
    """Dohvati narukvice s dodijeljenim korisnicima"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("""
                SELECT z.id AS zona_id, z.naziv AS zona_naziv,
                       k.id AS korisnik_id, k.ime, k.soba
                FROM zone z
                LEFT JOIN korisnici k ON z.korisnik_id = k.id
                ORDER BY z.id
            """, conn)
    except Exception as e:
        st.error(f"Greška pri dohvaćanju zona: {e}")
        return pd.DataFrame()

def kreiraj_i_dodijeli_korisnika(zona_id, ime, soba):
    """Kreiraj novog korisnika i odmah ga dodijeli zoni"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Kreiraj novog korisnika
            cur = conn.execute("INSERT INTO korisnici (ime, soba) VALUES (?, ?)", (ime, soba))
            korisnik_id = cur.lastrowid
            
            # Odmah ga dodijeli zoni
            conn.execute("UPDATE narukvice SET korisnik_id = ? WHERE id = ?", (korisnik_id, zona_id))
            conn.commit()
        return True, korisnik_id
    except Exception as e:
        st.error(f"Greška pri kreiranju korisnika: {e}")
        return False, None

def otkvaci_korisnika_od_zone(zona_id):
    """Otkvači korisnika od narukvice (korisnik ostaje u tablici)"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE narukvice SET korisnik_id = NULL WHERE id = ?", (zona_id,))
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri otkvačivanju korisnika: {e}")
        return False

def izbrisi_korisnika_iz_zone(zona_id, korisnik_id):
    """Izbriši korisnika iz tablice i otkvači od narukvice"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Prvo otkvači od narukvice
            conn.execute("UPDATE narukvice SET korisnik_id = NULL WHERE id = ?", (zona_id,))
            # Zatim izbriši korisnika iz tablice
            conn.execute("DELETE FROM korisnici WHERE id = ?", (korisnik_id,))
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri brisanju korisnika: {e}")
        return False

def get_slobodni_korisnici():
    """Dohvati korisnike koji nisu dodijeljeni nijednoj zoni"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("""
                SELECT k.id, k.ime, k.soba 
                FROM korisnici k 
                LEFT JOIN zone z ON k.id = z.korisnik_id 
                WHERE z.korisnik_id IS NULL
                ORDER BY k.ime
            """, conn)
    except Exception as e:
        st.error(f"Greška pri dohvaćanju slobodnih korisnika: {e}")
        return pd.DataFrame()

def povezi_korisnika_na_zonu(zona_id, korisnik_id):
    """Poveži postojećeg slobodnog korisnika s zonom"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE zone SET korisnik_id = ? WHERE id = ?", (korisnik_id, zona_id))
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri povezivanju: {e}")
        return False

# Main content - Zone management
zone_df = get_zone_data()
slobodni_korisnici_df = get_slobodni_korisnici()

if zone_df.empty:
    st.warning("⚠️ Nema definiranih narukvica u sustavu.")
    st.info("💡 Narukvice se kreiraju kroz AX PRO sustav ili admin panel.")
else:
    # Statistike narukvica
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("� Ukupno narukvica", len(zone_df))
    with col2:
        povezane = len(zone_df[zone_df['korisnik_id'].notna()])
        st.metric("� Dodijeljene narukvice", povezane)
    with col3:
        nepovezane = len(zone_df) - povezane
        st.metric("⚪ Slobodne narukvice", nepovezane)
    
    st.markdown("---")
    
    #################### Filter zones #####################
    filter_option = st.selectbox(
        "🔍 Filtriraj narukvice:",
        ["Sve narukvice", "Povezane narukvice", "Nepovezane narukvice"]
    )
    
    if filter_option == "Povezane narukvice":
        zone_df = zone_df[zone_df['korisnik_id'].notna()]
    elif filter_option == "Nepovezane narukvice":
        zone_df = zone_df[zone_df['korisnik_id'].isna()]
    
    if zone_df.empty:
        st.info(f"ℹ️ Nema narukvica u kategoriji '{filter_option}'.")
    else:
        st.subheader(f"� Narukvice ({len(zone_df)})")
        
        # Display zones with new management options
        for _, row in zone_df.iterrows():
            zona_id = row["zona_id"]
            zona_naziv = row["zona_naziv"]
            korisnik_id = row["korisnik_id"]
            korisnik_ime = row["ime"]
            korisnik_soba = row["soba"]
            
            # Narukvica status - ispravljena logika za pandas NaN
            narukvica_status = "🟢" if (pd.notna(korisnik_id) and korisnik_ime) else "⚪"
            
            # Prikaz korisnika sa sobom ako postoji
            if pd.notna(korisnik_id):
                korisnik_info = f"{korisnik_ime}"
                if korisnik_soba:
                    korisnik_info += f" (Soba: {korisnik_soba})"
            else:
                korisnik_info = "Nema korisnika"
            
            ###################### Prikaz narukvice 
            with st.expander(f"{narukvica_status} Narukvica: {zona_id} → {korisnik_info}"):
                
                if pd.notna(korisnik_id):  # Narukvica ima korisnika
                    st.markdown(f"**Trenutni korisnik:** {korisnik_ime}")
                    if korisnik_soba:
                        st.markdown(f"**Soba:** {korisnik_soba}")
                    
                    # Opcije za narukvice s korisnicima
                    akcija = st.radio(
                        "Odaberi akciju:",
                        ["Editiraj korisnika", "Otkvači korisnika", "Izbriši korisnika"],
                        key=f"akcija_{zona_id}"
                    )
                    
                    if akcija == "Editiraj korisnika":
                        with st.form(f"edit_korisnik_{zona_id}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                novo_ime = st.text_input("Ime:", value=korisnik_ime, key=f"edit_ime_{zona_id}")
                            with col2:
                                nova_soba = st.text_input("Soba:", value=korisnik_soba or "", key=f"edit_soba_{zona_id}")
                            
                            if st.form_submit_button("💾 Spremi promjene", use_container_width=True):
                                if update_korisnik(korisnik_id, novo_ime.strip(), nova_soba.strip() or None):
                                    st.success("✅ Korisnik ažuriran!")
                                    st.rerun()
                    
                    elif akcija == "Otkvači korisnika":
                        st.warning("⚠️ Korisnik će biti otkvačen od narukvice ali ostati u tablici korisnika.")
                        if st.button(f"🔓 Otkvači korisnika", key=f"otkvaci_{zona_id}", use_container_width=True):
                            if otkvaci_korisnika_od_zone(zona_id):
                                st.success("✅ Korisnik otkvačen od narukvice!")
                                st.rerun()
                    
                    elif akcija == "Izbriši korisnika":
                        st.error("❌ Korisnik će biti potpuno izbrisan iz sustava!")
                        if st.button(f"🗑️ Izbriši korisnika", key=f"delete_{zona_id}", type="secondary", use_container_width=True):
                            if izbrisi_korisnika_iz_zone(zona_id, korisnik_id):
                                st.success("✅ Korisnik izbrisan!")
                                st.rerun()
                
                else:  # Narukvica je prazna
                    st.info("⚪ Narukvica nema dodijeljenog korisnika")
                    
                    # Opcije za prazne narukvice
                    if len(slobodni_korisnici_df) > 0:
                        opcija = st.radio(
                            "Odaberi opciju:",
                            ["Dodijeli postojećeg korisnika", "Kreiraj novog korisnika"],
                            key=f"opcija_{zona_id}"
                        )
                    else:
                        st.info("💡 Nema slobodnih korisnika - možete kreirati novog")
                        opcija = "Kreiraj novog korisnika"
                    
                    if opcija == "Dodijeli postojećeg korisnika" and len(slobodni_korisnici_df) > 0:
                        # Select from available users
                        slobodni_korisnici_df["prikaz"] = slobodni_korisnici_df.apply(
                            lambda r: f"{r['ime']}" + (f" (Soba {r['soba']})" if pd.notna(r['soba']) and r['soba'] else ""),
                            axis=1
                        )
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            selected_korisnik = st.selectbox(
                                "Odaberi korisnika:",
                                options=slobodni_korisnici_df['id'].tolist(),
                                format_func=lambda x: slobodni_korisnici_df[slobodni_korisnici_df['id']==x]['prikaz'].iloc[0],
                                key=f"select_existing_{zona_id}"
                            )
                        with col2:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("� Dodijeli", key=f"assign_{zona_id}", use_container_width=True):
                                if povezi_korisnika_na_zonu(zona_id, selected_korisnik):
                                    st.success("✅ Korisnik dodijeljen zoni!")
                                    st.rerun()
                    
                    elif opcija == "Kreiraj novog korisnika":
                        # Create new user
                        with st.form(f"kreiraj_korisnik_{zona_id}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                novo_ime = st.text_input("Ime korisnika:", key=f"novo_ime_{zona_id}")
                            with col2:
                                nova_soba = st.text_input("Soba:", key=f"nova_soba_{zona_id}")
                            
                            if st.form_submit_button("➕ Kreiraj i dodijeli zoni", use_container_width=True):
                                if not novo_ime.strip():
                                    st.error("❌ Ime je obavezno!")
                                else:
                                    success, new_korisnik_id = kreiraj_i_dodijeli_korisnika(
                                        zona_id, novo_ime.strip(), nova_soba.strip() or None
                                    )
                                    if success:
                                        st.success(f"✅ Korisnik '{novo_ime}' kreiran i dodijeljen zoni!")
                                        st.rerun()

st.markdown("---")
st.markdown("<sub>© Robert M., 2025 – Admin Panel za Alarmni Sustav</sub>", unsafe_allow_html=True)