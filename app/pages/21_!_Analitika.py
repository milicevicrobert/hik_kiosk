# pages/21_Analitika_rada.py

import sqlite3
import time
from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st
from admin_config import DB_PATH  # prilagodi po potrebi (npr. nice_config)

st.set_page_config(page_title="📈 Analitika rada", page_icon="📈", layout="wide")

# ------------------ POMOĆNE ------------------
TIME_FMT = "%Y-%m-%d %H:%M:%S"

def _to_epoch(text_dt: Optional[str]) -> int:
    if not text_dt:
        return 0
    try:
        return int(datetime.strptime(text_dt, TIME_FMT).timestamp())
    except Exception:
        return 0

def _age_minutes(epoch_ts: int) -> Optional[int]:
    if not epoch_ts:
        return None
    return int((time.time() - epoch_ts) // 60)

@st.cache_data(ttl=5)
def _connect_info() -> dict:
    return {"db": DB_PATH}

def _conn():
    return sqlite3.connect(DB_PATH)

def _table_has_col(conn: sqlite3.Connection, table: str, col: str) -> bool:
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return any(r[1] == col for r in cur.fetchall())
    except Exception:
        return False

def _read_df(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> pd.DataFrame:
    try:
        return pd.read_sql_query(sql, conn, params=params)
    except Exception:
        return pd.DataFrame()

def _comm_get(conn: sqlite3.Connection, key: str) -> Optional[int]:
    try:
        row = conn.execute("SELECT value FROM comm WHERE key=?", (key,)).fetchone()
        return int(row[0]) if row and row[0] is not None else None
    except Exception:
        return None

# ------------------ HEADER ------------------
info = _connect_info()
st.title("📈 Analitika rada sustava — pregled u jednom ekranu")
st.caption(f"DB: `{info['db']}`")

# ------------------ UČITAVANJE PODATAKA ------------------
with _conn() as conn:
    have_cooldown_text = _table_has_col(conn, "zone", "cooldown_until")

    # Aktivne zone na centrali (status=1)
    active_zones_sql = f"""
        SELECT id, naziv, korisnik_id, alarm_status, last_alarm_time, last_updated
               {", cooldown_until" if have_cooldown_text else ""}
        FROM zone
        WHERE alarm_status = 1
        ORDER BY COALESCE(last_alarm_time, last_updated) DESC
    """
    df_zones_active = _read_df(conn, active_zones_sql)

    # Sve zone (treba nam za mismatch-e)
    all_zones_sql = f"""
        SELECT id, naziv, korisnik_id, alarm_status, last_alarm_time, last_updated
               {", cooldown_until" if have_cooldown_text else ""}
        FROM zone
    """
    df_zones_all = _read_df(conn, all_zones_sql)

    # Aktivni alarmi (nepotvrđeni)
    df_alarms_active = _read_df(
        conn,
        """
        SELECT id, zone_id, zone_name, vrijeme, korisnik, soba
        FROM alarms
        WHERE potvrda = 0
        ORDER BY vrijeme DESC
        """,
    )

    # Heartbeat-ovi
    hb_scanner = _comm_get(conn, "scanner_heartbeat")
    hb_kiosk = _comm_get(conn, "kiosk_heartbeat")

# ------------------ METRIKE (kvantitativno) ------------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🔔 Aktivni alarmi", len(df_alarms_active))
with col2:
    st.metric("📡 Zone u ALARMU (centrala)", len(df_zones_active))
with col3:
    age_s = _age_minutes(hb_scanner or 0)
    st.metric("🫀 Scanner heartbeat (min ago)", age_s if age_s is not None else "—")
with col4:
    age_k = _age_minutes(hb_kiosk or 0)
    st.metric("🫀 Kiosk heartbeat (min ago)", age_k if age_k is not None else "—")

if hb_scanner is None or (age_s is not None and age_s > 2):
    st.warning("⚠️ Scanner heartbeat nije svjež (možda servis ne radi).")
if hb_kiosk is None or (age_k is not None and age_k > 2):
    st.info("ℹ️ Kiosk heartbeat nije svjež (tablet možda nije spojen).")

st.divider()

# ------------------ KVALITATIVNE PROVJERE / MISMATCHI ------------------
st.subheader("🧪 Kvalitativne provjere (usklađenost centrale i alarma)")

# Zone u alarmu na centrali:
zone_ids_in_alarm = set(df_zones_active["id"].tolist()) if not df_zones_active.empty else set()
# Zone koje imaju aktivan red u alarms:
zone_ids_with_active_alarm = set(df_alarms_active["zone_id"].tolist()) if not df_alarms_active.empty else set()

zones_alarm_no_row = sorted(list(zone_ids_in_alarm - zone_ids_with_active_alarm))
alarms_row_no_zone = sorted(list(zone_ids_with_active_alarm - zone_ids_in_alarm))

cols = st.columns(2)
with cols[0]:
    st.markdown("**Zone u ALARM statusu bez aktivnog reda u `alarms`**")
    if zones_alarm_no_row:
        st.code(", ".join(map(str, zones_alarm_no_row)))
    else:
        st.success("Nema — sve zone u alarmu imaju aktivan zapis u `alarms`.")
with cols[1]:
    st.markdown("**Aktivni redovi u `alarms` za zone koje nisu u ALARM statusu**")
    if alarms_row_no_zone:
        st.code(", ".join(map(str, alarms_row_no_zone)))
    else:
        st.success("Nema — nema 'siročića' u `alarms`.")

st.markdown("---")

# ------------------ TABLICE: detaljni prikaz (kvantitativno + kontekst) ------------------

# Aktivne zone (centrala)
st.subheader("📡 Aktivne zone na centrali (zone.alarm_status = 1)")
if df_zones_active.empty:
    st.success("Nema zona u alarmu.")
else:
    df_show = df_zones_active.copy()
    # starosti u minutama
    df_show["age_last_alarm_time_min"] = df_show["last_alarm_time"].map(_to_epoch).map(_age_minutes)
    df_show["age_last_updated_min"] = df_show["last_updated"].map(_to_epoch).map(_age_minutes)
    if have_cooldown_text:
        df_show["cooldown_until_epoch"] = df_show["cooldown_until"].map(_to_epoch)
        now_ts = int(time.time())
        df_show["cooldown_in_future"] = df_show["cooldown_until_epoch"].apply(lambda x: (x or 0) > now_ts)
        df_show["cooldown_minutes_left"] = df_show["cooldown_until_epoch"].apply(
            lambda x: int((x - now_ts) // 60) if x and x > now_ts else 0
        )
    cols_order = [
        "id", "naziv", "korisnik_id",
        "last_alarm_time", "age_last_alarm_time_min",
        "last_updated", "age_last_updated_min",
    ]
    if have_cooldown_text:
        cols_order += ["cooldown_until", "cooldown_minutes_left", "cooldown_in_future"]
    st.dataframe(df_show[cols_order], use_container_width=True, hide_index=True)

st.markdown("---")

# Aktivni alarmi
st.subheader("🚨 Aktivni alarmi (alarms.potvrda = 0)")
if df_alarms_active.empty:
    st.success("Nema aktivnih alarma.")
else:
    dfA = df_alarms_active.copy()
    dfA["age_min"] = dfA["vrijeme"].map(_to_epoch).map(_age_minutes)
    st.dataframe(
        dfA[["id", "zone_id", "zone_name", "vrijeme", "age_min", "korisnik", "soba"]],
        use_container_width=True, hide_index=True
    )

st.markdown("---")

# Krš-križ pregled: zone vs alarms, s kontekstom
st.subheader("🧭 Krš-križ pregled (zone ↔ alarms) s kontekstom")
if not zones_alarm_no_row and not alarms_row_no_zone:
    st.success("Sve je usklađeno između centrale i `alarms` zapisa.")
else:
    c1, c2 = st.columns(2)
    if zones_alarm_no_row:
        with c1:
            st.markdown("**Zone u alarmu bez aktivnog reda u `alarms` — detalji**")
            df = df_zones_all[df_zones_all["id"].isin(zones_alarm_no_row)].copy()
            df["last_alarm_age_min"] = df["last_alarm_time"].map(_to_epoch).map(_age_minutes)
            df["last_updated_age_min"] = df["last_updated"].map(_to_epoch).map(_age_minutes)
            if have_cooldown_text:
                df["cooldown_until_epoch"] = df["cooldown_until"].map(_to_epoch)
            cols = ["id", "naziv", "korisnik_id", "alarm_status", "last_alarm_time", "last_alarm_age_min",
                    "last_updated", "last_updated_age_min"]
            if have_cooldown_text:
                cols += ["cooldown_until"]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)

    if alarms_row_no_zone:
        with c2:
            st.markdown("**Aktivni redovi u `alarms` bez zone u alarmu — detalji**")
            df = df_alarms_active[df_alarms_active["zone_id"].isin(alarms_row_no_zone)].copy()
            df["age_min"] = df["vrijeme"].map(_to_epoch).map(_age_minutes)
            st.dataframe(df[["id", "zone_id", "zone_name", "vrijeme", "age_min", "korisnik", "soba"]],
                         use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Sve informacije se učitavaju jednim osvježavanjem stranice (cache ttl=5s).")
