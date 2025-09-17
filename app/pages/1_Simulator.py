# simulator_centrale.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from admin_config import DB_PATH
import time
import random

# ------------------ UI CONFIG ------------------
st.set_page_config(
    page_title="Simulator AX PRO centrale",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Hide Streamlit menu / toolbar
st.markdown(
    """
    <style>
        div[data-testid="stToolbar"] button { display: none !important; }
        .main > div { padding-top: 1.25rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧪 Simulator centrale (AX PRO mock)")
st.caption(
    "Ovaj simulator pali/gasi alarme na ZONAMA (tablica `zone`). Kiosk će iz toga sam kreirati zapise u `alarms`."
)
st.markdown("---")


# ------------------ DB HELPERS ------------------
def connect():
    return sqlite3.connect(DB_PATH)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_sve_zone(include_user=True) -> pd.DataFrame:
    """
    Dohvati sve zone; po želji pridruži korisnika/sobu (ako tablica korisnici postoji).
    """
    try:
        with connect() as conn:
            if include_user:
                # LEFT JOIN kako bismo pokrili i zone bez korisnika
                q = """
                SELECT 
                    z.id                AS zone_id,
                    z.naziv             AS zone_naziv,
                    z.alarm_status      AS alarm_status,
                    z.last_alarm_time   AS last_alarm_time,
                    z.last_updated      AS last_updated,
                    k.ime               AS korisnik_ime,
                    k.soba              AS soba
                FROM zone z
                LEFT JOIN korisnici k ON z.korisnik_id = k.id
                ORDER BY z.id;
                """
            else:
                q = "SELECT id AS zone_id, naziv AS zone_naziv, alarm_status, last_alarm_time, last_updated FROM zone ORDER BY id;"
            df = pd.read_sql_query(q, conn)
        return df
    except Exception as e:
        st.error(f"Greška pri dohvaćanju zona: {e}")
        return pd.DataFrame()


def set_zone_alarm(zone_id: int, on: bool, set_time: bool = True) -> bool:
    """
    Simulira centralu: pali/gasi alarm na zoni.
    - ON: alarm_status=1 (+ last_alarm_time=NOW po potrebi)
    - OFF: alarm_status=0
    """
    try:
        ts = now_str()
        with connect() as conn:
            cur = conn.cursor()
            if on:
                if set_time:
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
                else:
                    cur.execute(
                        """
                        UPDATE zone
                        SET alarm_status = 1,
                            last_updated = ?
                        WHERE id = ?
                        """,
                        (ts, zone_id),
                    )
            else:
                cur.execute(
                    """
                    UPDATE zone
                    SET alarm_status = 0,
                        last_updated = ?
                    WHERE id = ?
                    """,
                    (ts, zone_id),
                )
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Greška pri simulaciji alarma: {e}")
        return False


def set_all_off() -> int:
    """Isključi sve alarme (alarm_status=0 za sve zone). Vraća broj pogođenih redaka."""
    try:
        ts = now_str()
        with connect() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE zone SET alarm_status = 0, last_updated = ?", (ts,))
            affected = cur.rowcount
            conn.commit()
        return affected or 0
    except Exception as e:
        st.error(f"Greška pri gašenju svih zona: {e}")
        return 0


def random_alarm_on() -> dict | None:
    """Uključi alarm na nasumičnoj zoni (Alarm ON)."""
    df = get_sve_zone(include_user=False)
    if df.empty:
        st.error("❌ Nema zona u bazi.")
        return None
    row = df.sample(1).iloc[0]
    zid = int(row["zone_id"])
    if set_zone_alarm(zid, on=True, set_time=True):
        return {"zone_id": zid, "zone_naziv": str(row["zone_naziv"])}
    return None


# ------------------ TABS ------------------
tab_sim, tab_overview, tab_tools = st.tabs(
    ["🚨 Simulator", "📋 Pregled Zona", "🛠️ Alati"]
)

# ------------------ TAB: SIMULATOR ------------------
with tab_sim:
    st.subheader("🚨 Generiranje događaja (centrala ➜ zone)")

    # Random alarm
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("**Random ALARM ON** — uključi alarm na nasumičnoj zoni")
        if st.button(
            "🎲 Generiraj Random ALARM (Alarm ON)",
            type="primary",
            use_container_width=True,
        ):
            res = random_alarm_on()
            if res:
                st.success(f"✅ Alarm ON: {res['zone_naziv']} (ID {res['zone_id']})")
                st.rerun()

    with c2:
        st.markdown("**Svi OFF** — ugasi sve alarme u zoni")
        if st.button(
            "🧹 Ugasi sve (Alarm OFF za sve zone)",
            type="secondary",
            use_container_width=True,
        ):
            n = set_all_off()
            st.success(f"✅ Ugašeno (OFF) na {n} zona.")
            st.rerun()

    st.markdown("---")

    # Ručno upravljanje jednom zonom
    df_zone = get_sve_zone(include_user=True)
    if df_zone.empty:
        st.info("📭 Nema zona za prikaz.")
    else:
        st.markdown("**Ručni ON/OFF**")

        colA, colB, colC, colD = st.columns([2, 1, 1, 1])

        with colA:
            selected_zone_id = st.selectbox(
                "Odaberite zonu:",
                options=df_zone["zone_id"].tolist(),
                format_func=lambda zid: f"{df_zone[df_zone['zone_id']==zid]['zone_naziv'].iloc[0]} (ID {zid})",
                key="sel_zone",
            )

        with colB:
            if st.button("🔴 Alarm ON", type="primary", use_container_width=True):
                if set_zone_alarm(selected_zone_id, on=True, set_time=True):
                    st.success("✅ Alarm ON")
                    st.rerun()

        with colC:
            if st.button("🟢 Alarm OFF", type="secondary", use_container_width=True):
                if set_zone_alarm(selected_zone_id, on=False):
                    st.success("✅ Alarm OFF")
                    st.rerun()

        with colD:
            secs = st.number_input(
                "Auto-OFF (sek)", min_value=1, max_value=300, value=30, step=1
            )
            if st.button("⏲️ Alarm ON ➜ Auto-OFF", use_container_width=True):
                # jednostavan demo (blokira tijekom čekanja)
                if set_zone_alarm(selected_zone_id, on=True, set_time=True):
                    st.info(f"⏳ Uključeno; gašenje za {secs} s…")
                    st.toast("Alarm ON", icon="🔴")
                    time.sleep(int(secs))
                    set_zone_alarm(selected_zone_id, on=False)
                    st.toast("Alarm OFF", icon="🟢")
                    st.success("✅ Auto-OFF izvršen")
                    st.rerun()

# ------------------ TAB: OVERVIEW ------------------
with tab_overview:
    st.subheader("📋 Trenutno stanje zona")
    df = get_sve_zone(include_user=True)
    if df.empty:
        st.info("📭 Nema zona za prikaz.")
    else:
        # Ljudski čitljiv status
        df_view = df.copy()
        df_view["status"] = df_view["alarm_status"].apply(
            lambda v: "🔴 ALARM" if int(v or 0) == 1 else "🟢 OK"
        )
        df_view = df_view[
            [
                "zone_id",
                "zone_naziv",
                "status",
                "last_alarm_time",
                "last_updated",
                "korisnik_ime",
                "soba",
            ]
        ].rename(
            columns={
                "zone_id": "ID",
                "zone_naziv": "Zona",
                "korisnik_ime": "Korisnik",
                "soba": "Soba",
                "last_alarm_time": "Zadnji alarm",
                "last_updated": "Zadnja promjena",
            }
        )
        st.dataframe(
            df_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn(format="%d"),
            },
        )

# ------------------ TAB: TOOLS ------------------
with tab_tools:
    st.subheader("🛠️ Alati / dijagnostika")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Ručno paljenje na X nasumičnih zona**")
        n = st.number_input("Broj zona (n):", min_value=1, value=1, step=1)
        if st.button("🎯 Uključi ALARM ON na n nasumičnih zona", type="primary"):
            df_all = get_sve_zone(include_user=False)
            if df_all.empty:
                st.error("Nema zona.")
            else:
                sample = df_all.sample(min(int(n), len(df_all)))
                ok_cnt = 0
                for _, r in sample.iterrows():
                    ok_cnt += (
                        1
                        if set_zone_alarm(int(r["zone_id"]), on=True, set_time=True)
                        else 0
                    )
                st.success(f"✅ Uključeno (ON) na {ok_cnt} zona.")
                st.rerun()

    with col2:
        st.markdown("**Gašenje svih zona**")
        if st.button("🧯 Ugasi sve (Alarm OFF)", type="secondary"):
            m = set_all_off()
            st.success(f"✅ Ugašeno (OFF) na {m} zona.")
            st.rerun()

st.markdown("---")
st.markdown(
    "<sub>Napomena: Simulator mijenja samo tablicu <code>zone</code>. Kiosk (NiceGUI) iz toga sam kreira zapise u <code>alarms</code>.</sub>",
    unsafe_allow_html=True,
)
