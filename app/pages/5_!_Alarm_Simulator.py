import streamlit as st
import sqlite3
import pandas as pd
import random
from datetime import datetime, date, timedelta
from admin_config import DB_PATH

st.set_page_config(
    page_title="Alarm Simulator",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
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

st.title("🚨 Upravljanje Alarmima")
st.caption("Simulacija alarma, pregled i upravljanje alarmnim sustavom")

st.markdown("---")

# Database read functions
def get_sve_zone():
    """Dohvati sve zone s njihovim korisnicima"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("""
                SELECT 
                    z.id as zone_id,
                    z.naziv as zone_naziv,
                    k.ime as korisnik_ime,
                    k.soba
                FROM zone z
                INNER JOIN korisnici k ON z.korisnik_id = k.id
                ORDER BY z.id
            """, conn)
    except Exception as e:
        st.error(f"Greška pri dohvaćanju zona: {e}")
        return pd.DataFrame()

def get_all_alarms(korisnik=None, osoblje=None, datum_od=None, datum_do=None):
    """Dohvati sve alarme s filterima"""
    try:
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
    except Exception as e:
        st.error(f"Greška pri dohvaćanju alarma: {e}")
        return pd.DataFrame()

def get_aktivni_alarms():
    """Dohvati sve aktivne (nepotvrđene) alarme"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("""
                SELECT 
                    id,
                    zone_id,
                    zone_name,
                    korisnik,
                    soba,
                    vrijeme,
                    CASE 
                        WHEN potvrda = 0 THEN '🔴 Aktivan'
                        ELSE '✅ Potvrđen'
                    END as status
                FROM alarms 
                WHERE potvrda = 0
                ORDER BY vrijeme DESC
            """, conn)
    except Exception as e:
        st.error(f"Greška pri dohvaćanju alarma: {e}")
        return pd.DataFrame()

def get_aktivno_osoblje():
    """Dohvati aktivno osoblje iz baze"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("""
                SELECT id, ime, sifra 
                FROM osoblje 
                WHERE aktivna = 1 
                ORDER BY ime
            """, conn)
    except Exception as e:
        st.error(f"Greška pri dohvaćanju osoblja: {e}")
        return pd.DataFrame()

# Database write functions
def insert_random_alarm():
    """Kreiraj random alarm - odaberi random zonu, zona već ima dodijeljenog korisnika"""
    try:
        df_zone = get_sve_zone()
        
        if df_zone.empty:
            st.error("❌ Nema zona s dodijeljenim korisnicima!")
            return False
        
        # Odaberi random zonu
        random_row = df_zone.sample(1).iloc[0]
        
        zone_id = int(random_row['zone_id'])  # Osiguraj da je integer
        zone_name = str(random_row['zone_naziv'])
        korisnik_ime = str(random_row['korisnik_ime'])
        soba = str(random_row['soba']) if pd.notna(random_row['soba']) else "N/A"
        
        # Provjeri postoji li već nepotvrđen alarm za ovu zonu
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM alarms WHERE zone_id = ? AND potvrda = 0", (zone_id,))
            already_active = cur.fetchone()[0] > 0
            
            if already_active:
                st.warning(f"⚠️ Zona '{zone_name}' već ima aktivan alarm!")
                return False
            
            # Unesi novi alarm
            cur.execute("""
                INSERT INTO alarms (zone_id, zone_name, vrijeme, korisnik, soba, potvrda)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (
                zone_id,
                zone_name,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                korisnik_ime,
                soba or "N/A"
            ))
            conn.commit()
            
            # Dohvati ID kreiranog alarma
            alarm_id = cur.lastrowid
            
            return {
                'alarm_id': alarm_id,
                'zone_id': zone_id,
                'zone_name': zone_name,
                'korisnik': korisnik_ime,
                'soba': soba or "N/A"
            }
            
    except Exception as e:
        st.error(f"Greška pri kreiranju alarma: {e}")
        return False

def confirm_alarm(alarm_id, osoblje_ime):
    """Potvrdi alarm"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE alarms 
                SET potvrda = 1, 
                    vrijemePotvrde = ?, 
                    osoblje = ?
                WHERE id = ?
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), osoblje_ime, alarm_id))
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Greška pri potvrdi alarma: {e}")
        return False

def reset_alarm(alarm_id):
    """Resetiranje (brisanje) alarma"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM alarms WHERE id = ?", (alarm_id,))
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Greška pri resetiranju alarma: {e}")
        return False

def delete_old_alarms(datum_brisi):
    """Obriši stare alarme"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM alarms WHERE DATE(vrijeme) < ?", (datum_brisi,))
            deleted_count = cur.rowcount
            conn.commit()
            return deleted_count
    except Exception as e:
        st.error(f"Greška pri brisanju alarma: {e}")
        return 0

# Main interface
tab1, tab2, tab3, tab4 = st.tabs(["🧪 Simulator", "🔴 Aktivni Alarmi", "📋 Pregled Alarma", "📊 Statistike"])

# Tab 1: Alarm Simulator - REORGANIZED
with tab1:
    st.markdown("### 🧪 Alarm Generator")
    st.caption("Generiraj test alarm i pogledaj rezultate")
    
    # Generator sekcija
    st.markdown("#### 🚨 Generator")
    
    df_zone = get_sve_zone()
    if not df_zone.empty:
        # Glavni generator button
        if st.button("🚨 Generiraj Random Alarm", type="primary", use_container_width=True, key="gen_alarm"):
            result = insert_random_alarm()
            if result:
                # Detaljni prikaz kreiranog alarma
                st.success("✅ **ALARM USPJEŠNO KREIRAN!**")
                
                # Highlight box s detaljima
                st.info(f"""
                🆔 **Alarm ID:** {result['alarm_id']}  
                📍 **Narukvica:** {result['zone_name']} (ID: {result['zone_id']})  
                👤 **Korisnik:** {result['korisnik']}  
                🏠 **Soba:** {result['soba']}  
                ⏰ **Vrijeme:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}  
                """)
                
                
                
    else:
        st.warning("⚠️ Nema dostupnih narukvica s korisnicima!")
        st.info("💡 Dodajte korisnike i narukvice u admin panelu")

# Tab 2: Active Alarms Management
with tab2:
    st.markdown("### 🔴 Aktivni Alarmi")
    
    # Get fresh data from database
    df_aktivni = get_aktivni_alarms()
    
    if not df_aktivni.empty:
        st.dataframe(
            df_aktivni[['zone_name', 'korisnik', 'soba', 'vrijeme', 'status']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "zone_name": "Narukvica",
                "korisnik": "Korisnik", 
                "soba": "Soba",
                "vrijeme": "Vrijeme",
                "status": "Status"
            }
        )
        
        # Management options
        st.markdown("#### 🛠️ Upravljanje")
        
        # Single alarm selector for both operations
        selected_alarm_id = st.selectbox(
            "Odaberi alarm:",
            options=df_aktivni['id'].tolist(),
            format_func=lambda x: f"{df_aktivni[df_aktivni['id']==x]['zone_name'].iloc[0]} - {df_aktivni[df_aktivni['id']==x]['korisnik'].iloc[0]}",
            key="shared_alarm_selector"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 🗑️ Reset Alarm")
            if st.button("🗑️ Reset Alarm", type="secondary", use_container_width=True):
                if reset_alarm(selected_alarm_id):
                    st.success("✅ Alarm resetiran!")
                    st.rerun()
        
        with col2:
            st.markdown("##### ✅ Potvrdi Alarm")
            
            osoblje_df = get_aktivno_osoblje()
            if not osoblje_df.empty:
                selected_osoblje_id = st.selectbox(
                    "Odaberi osoblje:",
                    options=osoblje_df['id'].tolist(),
                    format_func=lambda x: f"{osoblje_df[osoblje_df['id']==x]['ime'].iloc[0]} ({osoblje_df[osoblje_df['id']==x]['sifra'].iloc[0]})",
                    key="osoblje_selector"
                )
                
                selected_osoblje_ime = osoblje_df[osoblje_df['id']==selected_osoblje_id]['ime'].iloc[0]
                
                if st.button("✅ Potvrdi Alarm", type="primary", use_container_width=True):
                    if confirm_alarm(selected_alarm_id, selected_osoblje_ime):
                        st.success("✅ Alarm potvrđen!")
                        st.rerun()
            else:
                st.warning("⚠️ Nema aktivnog osoblja u bazi")
                st.info("💡 Dodajte osoblje u admin panelu")
        
        # Reset all button with confirmation checkbox
        st.markdown("---")
        
        
        if st.button("🗑️ Reset Svih Aktivnih Alarma", type="secondary", use_container_width=True):
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM alarms WHERE potvrda = 0")
                    deleted_count = cur.rowcount
                    conn.commit()
                
                st.success(f"✅ Resetirano {deleted_count} alarma!")
                st.rerun()
                
            except Exception as e:
                st.error(f"Greška pri resetiranju: {e}")
        
    else:
        st.info("✅ Nema aktivnih alarma")

# Tab 3: Alarm History & Search
with tab3:
    st.markdown("### 📋 Pregled i Pretraživanje Alarma")
    
    # Filters
    with st.expander("🔎 Filteri", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filter_korisnik = st.text_input("Korisnik")
        with col2:
            filter_osoblje = st.text_input("Osoblje")
        with col3:
            filter_datum_od = st.date_input("Datum od", value=date.today())
        with col4:
            filter_datum_do = st.date_input("Datum do", value=date.today())

    # Convert dates to strings
    if filter_datum_od and filter_datum_do:
        datum_od_str = filter_datum_od.strftime("%Y-%m-%d")
        datum_do_str = filter_datum_do.strftime("%Y-%m-%d")
    else:
        datum_od_str = None
        datum_do_str = None

    st.caption(f"Prikaz od {datum_od_str or '-'} do {datum_do_str or '-'}")

    # Get filtered alarms
    alarms_df = get_all_alarms(filter_korisnik, filter_osoblje, datum_od_str, datum_do_str)

    if alarms_df.empty:
        st.info("📭 Nema alarma za zadane filtere")
    else:
        # Display results
        st.dataframe(
            alarms_df,
            use_container_width=True,
            column_config={
                "zone_name": "Narukvica",
                "korisnik": "Korisnik",
                "soba": "Soba", 
                "vrijeme": "Vrijeme",
                "potvrda": st.column_config.CheckboxColumn("Potvrđen"),
                "vrijemePotvrde": "Vrijeme potvrde",
                "osoblje": "Osoblje"
            }
        )
        st.markdown(f"**Broj prikazanih alarma:** {len(alarms_df)}")
        
        # Download CSV
        csv = alarms_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Preuzmi CSV",
            data=csv,
            file_name=f"alarmi_{datum_od_str}_{datum_do_str}.csv",
            mime="text/csv"
        )

    # Delete old alarms section
    st.markdown("---")
    with st.expander("🗑️ Brisanje Starih Alarma", expanded=False):
        st.warning("⚠️ Ova operacija je nepovratna!")
        
        datum_brisi = st.date_input("Obriši sve alarme starije od:", value=date.today())
        datum_brisi_str = datum_brisi.strftime("%Y-%m-%d")
        
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM alarms WHERE DATE(vrijeme) < ?", (datum_brisi_str,))
                broj_za_brisanje = cur.fetchone()[0]
        except:
            broj_za_brisanje = 0
            
        st.info(f"Broj alarma za brisanje: **{broj_za_brisanje}**")
        
        if broj_za_brisanje > 0:
            if st.button("🗑️ Obriši Stare Alarme", type="secondary"):
                deleted_count = delete_old_alarms(datum_brisi_str)
                if deleted_count > 0:
                    st.success(f"✅ Obrisano {deleted_count} alarma")
                    st.rerun()

# Tab 4: Statistics
with tab4:
    st.markdown("### 📊 Statistike Alarma")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            
            # Today's statistics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                cur.execute("SELECT COUNT(*) FROM alarms WHERE DATE(vrijeme) = DATE('now')")
                alarms_today = cur.fetchone()[0]
                st.metric("🚨 Alarmi danas", alarms_today)
            
            with col2:
                cur.execute("SELECT COUNT(*) FROM alarms WHERE potvrda = 0")
                active_alarms = cur.fetchone()[0]
                st.metric("🔴 Aktivni alarmi", active_alarms)
            
            with col3:
                cur.execute("""
                    SELECT COUNT(DISTINCT k.id) 
                    FROM korisnici k 
                    INNER JOIN zone z ON k.id = z.korisnik_id
                """)
                users_with_zones = cur.fetchone()[0]
                st.metric("👥 Korisnici s narukvicama", users_with_zones)
            
            with col4:
                cur.execute("SELECT COUNT(*) FROM zone")
                total_zones = cur.fetchone()[0]
                st.metric("📿 Ukupno narukvica", total_zones)
            
            # Weekly statistics
            st.markdown("#### 📈 Tjedne Statistike")
            
            weekly_stats = pd.read_sql_query("""
                SELECT 
                    DATE(vrijeme) as datum,
                    COUNT(*) as broj_alarma,
                    SUM(CASE WHEN potvrda = 1 THEN 1 ELSE 0 END) as potvrđeni,
                    SUM(CASE WHEN potvrda = 0 THEN 1 ELSE 0 END) as nepotvrđeni
                FROM alarms 
                WHERE DATE(vrijeme) >= DATE('now', '-7 days')
                GROUP BY DATE(vrijeme)
                ORDER BY datum DESC
            """, conn)
            
            if not weekly_stats.empty:
                st.dataframe(weekly_stats, use_container_width=True)
                
                # Chart
                st.line_chart(weekly_stats.set_index('datum')[['potvrđeni', 'nepotvrđeni']])
            else:
                st.info("📭 Nema podataka za zadnjih 7 dana")
                
    except Exception as e:
        st.error(f"Greška pri dohvaćanju statistika: {e}")

# Footer
st.markdown("---")
st.markdown("<sub>💡 Ovaj sustav kombinira simulator alarma s punim upravljanjem alarmnog sustava</sub>", unsafe_allow_html=True)