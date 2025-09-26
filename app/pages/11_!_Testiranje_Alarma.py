import sqlite3
import streamlit as st
from admin import DB_PATH
import pandas as pd
from datetime import datetime
from module.axpro_auth import (
    login_axpro,
    get_zone_status,
    clear_axpro_alarms,
)

st.set_page_config(page_title="Alarm Axpro", page_icon="📈", layout="wide")

# ------------------ POMOĆNE ------------------
TIME_FMT = "%Y-%m-%d %H:%M:%S"


# ----------- SPAJANJE NA CENTERALU -----------
def get_axpro_data():
    cookie = login_axpro()
    if not cookie:
        st.error("Neuspješna prijava na Axpro centralu.")
        return None
    zones = get_zone_status(cookie)
    if zones is None:
        st.error("Neuspješno dohvaćanje statusa zona.")
        return None
    zone_list = [z["Zone"] for z in zones.get("ZoneList", [])]
    df = pd.DataFrame(zone_list)
    df = df[df["alarm"] == 1]  # Filtrirajaj samo aktivne alarme
    return df

# ----------- UPRAVLJANJE ALARMIMA -----------

def confirm_alarm(alarm_id, osoblje_ime):
    """Upiši u db.alarms potvrdu vrijeme potvrde, osobu koja je potvrdila"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE alarms 
                SET potvrda = 1, 
                    vrijemePotvrde = ?, 
                    osoblje = ?
                WHERE id = ?
            """,
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), osoblje_ime, alarm_id),
            )
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Greška pri potvrdi alarma: {e}")
        return False


def set_zone_alarm(zone_id: int) -> bool:
    """Uključi alarm na jednoj zoni (postavi alarm_status=1)."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE zone
                SET alarm_status = 1,
                    last_alarm_time = ?,
                    last_updated = ?
                WHERE id = ?
                """,
                (ts, ts, zone_id),
            )
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri simulaciji alarma: {e}")
        return False

def reset_zone_alarms() -> bool:
    """Isključi sve alarme u svim zonama (postavi alarm_status=0 za sve)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE zone
                SET alarm_status = 0
                """
            )
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri resetiranju svih alarma: {e}")
        return False

# ------------------ UČITAVANJE PODATAKA ------------------
def query(sql: str) -> pd.DataFrame:
    """Izvrši SELECT upit i vrati rezultat kao DataFrame."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(sql, conn)
    except Exception as e:
        st.error(f"Greška pri učitavanju podataka iz baze: {e}")
        return pd.DataFrame()


# ------------------ SQL upiti ------------------
sqlz = """
    SELECT * FROM zone 
    WHERE alarm_status = 1
    ORDER BY COALESCE(last_alarm_time, last_updated) DESC;
"""

sqla = """
    SELECT * FROM alarms 
    WHERE potvrda = 0
    ORDER BY vrijeme DESC;
"""
sql_osoblje = """
    SELECT id, ime, sifra 
    FROM osoblje 
    WHERE aktivna = 1 
    ORDER BY ime;
"""
sql_sveZone = """
    SELECT * FROM zone
    ORDER BY id;
"""

#------------------ GLAVNI PROGRAM ------------------
# Učitavanje podataka u df.
df_zone_aktivne = query(sqlz)
df_alarm_aktivni = query(sqla)
df_zone = query(sql_sveZone)
df_osoblje = query(sql_osoblje)

if st.sidebar.button("🔄 Osvježi prikaz"):
    st.rerun()
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
 
# Naslov
st.subheader("📈 Alarm Axpro — pregled stanja alarma")
st.markdown("---")

# Tablica zone

st.markdown(
    f"""
    <span style='font-size:1em; color:lightgrey; font-weight:500; letter-spacing:0.2px;'>
        Aktivne zone (db.zone, alarm_status=1): 
        <span style='background:#ffebee; color:#c62828; border-radius:6px; 
                     padding:0.18em 0.9em; font-weight:700; font-size:1.08em; margin-left:0.7em;'>
            {len(df_zone_aktivne)}
        </span>
    </span>
    """,
    unsafe_allow_html=True,
)
st.dataframe(df_zone_aktivne, width='stretch')


if df_zone.empty:
    st.info("Nema zona za prikaz.")
else:
    col1,col2,col3= st.columns([2,1,1])
    with col1:
        selected_zone_id = st.selectbox(
            "Zona",
            options=df_zone["id"].tolist(),
            format_func=lambda zid: f"{df_zone[df_zone['id']==zid]['naziv'].iloc[0]} ID {zid}",
            key="sel_zone",
            label_visibility="collapsed",
        )

    with col2:

        if st.button(
            "Uključi alarm ", type="primary", width="stretch"
        ):
            if set_zone_alarm(selected_zone_id):
                st.success("Alarm uključen")
                st.rerun()
    with col3:
        if st.button(
            "Isključi alarm ", type="secondary", width="stretch"
        ):
            if reset_zone_alarms():
                st.success("Alarm isključen")
                st.rerun()
st.markdown("---")

# Tablica alarmi

st.markdown(
    f"""
    <span style='font-size:1em; color:lightgrey; font-weight:500; letter-spacing:0.2px;'>
        Aktivni alarmi (db.alarms, potvrda=0):
        <span style='background:#ffebee; color:#c62828; border-radius:6px; 
                     padding:0.18em 0.9em; font-weight:700; font-size:1.08em; margin-left:0.7em;'>
            {len(df_alarm_aktivni)}
        </span>
    </span>
    """,
    unsafe_allow_html=True,
)

st.dataframe(df_alarm_aktivni, width='stretch')
#Reset alarma
 # Management options

# Single alarm selector for both operations
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    selected_alarm_id = st.selectbox(
        "Odaberi alarm:",
        options=df_alarm_aktivni["id"].tolist(),
        format_func=lambda x: f"{df_alarm_aktivni[df_alarm_aktivni['id']==x]['zone_name'].iloc[0]} - {df_alarm_aktivni[df_alarm_aktivni['id']==x]['korisnik'].iloc[0]}",
        key="shared_alarm_selector", label_visibility="collapsed"
    )
with col2:
    
    selected_osoblje_id = st.selectbox(
        "Odaberi osoblje:",
        options=df_osoblje["id"].tolist(),
        format_func=lambda x: f"{df_osoblje[df_osoblje['id']==x]['ime'].iloc[0]} ({df_osoblje[df_osoblje['id']==x]['sifra'].iloc[0]})",
        key="osoblje_selector",label_visibility="collapsed"
    )
    selected_osoblje_ime = df_osoblje[df_osoblje["id"] == selected_osoblje_id]["ime"].iloc[0]

with col3:
    if st.button("✅ Potvrdi Alarm", type="primary", width="stretch"):
        if confirm_alarm(selected_alarm_id, selected_osoblje_ime):
            st.success("✅ Alarm potvrđen!")
            st.rerun()

st.markdown("---")


#Tablica Axpro centrla

if st.button("🔄 Dohvati podatke s centrale", type="primary", width='content'):
    try:
        with st.spinner("Dohvaćanje podataka s Axpro centrale..."):
            df_axpro = get_axpro_data()
    except Exception as e:
        st.error(f"Greška pri dohvaćanju podataka s Axpro centrale: {e}")
        df_axpro = None
    if df_axpro is not None:
        st.subheader("Aktivne zone Axpro (alarm_status=1)")
        st.dataframe(df_axpro, width='stretch')
        if not df_axpro.empty:
            if st.button("Očisti sve alarme na Axpro centralu", width='content'):
                cookie = login_axpro()
                if cookie:
                    success = clear_axpro_alarms(cookie)
                    if success:
                        st.success("Uspješno očišćeni svi alarmi na Axpro centralu.")
                    else:
                        st.error("Neuspješno čišćenje alarma na Axpro centralu.")
                else:
                    st.error("Neuspješna prijava na Axpro centralu.")
st.caption("© 2024 by RM")

#Reset centrale
