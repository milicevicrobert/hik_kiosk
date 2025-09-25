import sqlite3
import streamlit as st
from module.config import DB_PATH
import pandas as pd
from datetime import datetime
from module.axpro_auth import (
    login_axpro,
    get_zone_status,
    clear_axpro_alarms,
)

st.set_page_config(page_title="📈 Alarm Axpro", page_icon="📈", layout="wide")

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

# ------------------ UČITAVANJE PODATAKA ------------------
with sqlite3.connect(DB_PATH) as conn:

    def query(sql: str) -> pd.DataFrame:
        try:
            return pd.read_sql_query(sql, conn)
        except Exception as e:
            st.error(f"Greška pri učitavanju podataka iz baze: {e}")
            return pd.DataFrame()

    def add_human_time_column(df, col_name="value", new_col="vrijeme_fmt"):
        """Dodaj novu kolonu u dataframe s human-readable vremenom iz epoch vremena."""
        df[new_col] = df[col_name].apply(
            lambda x: datetime.fromtimestamp(int(x)).strftime(TIME_FMT) if x else None
        )
        return df.drop(columns=[col_name])

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
    sqlc = """
        SELECT * FROM comm
        WHERE key IN ("scanner_heartbeat", "kiosk_heartbeat");
    """

    sql_resetAlarm = """
        SELECT value FROM comm
        WHERE key = 'resetAlarm';
    """

    df_zone_aktivne = query(sqlz)
    df_alarm_aktivni = query(sqla)

    df_comm = query(sqlc)
    df_comm = add_human_time_column(df_comm, col_name="value")

    reset_alarm = conn.execute(sql_resetAlarm).fetchone()
    reset_alarm = int(reset_alarm[0]) if reset_alarm else None

# ------------------ HEADER ------------------
st.header("📈 Alarm Axpro — pregled stanja alarma")
st.caption(f"DB: `{DB_PATH}`")

# ------------------ PRIKAZ PODATAKA ------------------

col1, col2 = st.columns(2)
with col1:
    st.subheader("Aktivne zone db.zone (alarm_status=1)")
with col2:
    st.metric("Aktivne zone db.zone", len(df_zone_aktivne))
st.dataframe(df_zone_aktivne, use_container_width=True)
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Aktivni alarmi db.alarms (potvrda=0)")
with col2:
    st.metric("Aktivni db.alarms (nepotvrđeni)", len(df_alarm_aktivni))
st.dataframe(df_alarm_aktivni, use_container_width=True)
st.markdown("---")
st.subheader("Ostali podaci iz db.comm")
st.dataframe(df_comm, use_container_width=True)

# ------------------ AXPRO ------------------

try:
    with st.spinner("Dohvaćanje podataka s Axpro centrale..."):
        df_axpro = get_axpro_data()
except Exception as e:
    st.error(f"Greška pri dohvaćanju podataka s Axpro centrale: {e}")
    df_axpro = None
if df_axpro is not None:
    st.subheader("Aktivne zone Axpro (alarm_status=1)")
    st.dataframe(df_axpro, use_container_width=True)
    if not df_axpro.empty:
        if st.button("Očisti sve alarme na Axpro centralu"):
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
