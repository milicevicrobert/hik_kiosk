# simulator_centrale.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from admin_config import DB_PATH
import time

# ------------------ Postavke sučelja ------------------
st.set_page_config(
    page_title="Simulator AX PRO centrale",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sakrij alatnu traku Streamlita radi čišćeg izgleda
st.markdown(
    """
    <style>
        div[data-testid="stToolbar"] button { display: none !important; }
        .main > div { padding-top: 1.0rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧪 Simulator centrale AX PRO")
st.caption(
    "Simulator uključuje i gasi alarme na zonama u tablici zone. Kiosk iz toga sam stvara zapise u tablici alarms."
)
st.markdown("---")


# ------------------ Pomoćne funkcije za bazu ------------------
def connect():
    return sqlite3.connect(DB_PATH)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_sve_zone(include_user=True) -> pd.DataFrame:
    """Dohvati sve zone, po želji s pridruženim korisnikom i sobom."""
    try:
        with connect() as conn:
            if include_user:
                q = """
                SELECT 
                    z.id               AS zone_id,
                    z.naziv            AS zone_naziv,
                    z.alarm_status     AS alarm_status,
                    z.last_alarm_time  AS last_alarm_time,
                    z.last_updated     AS last_updated,
                    k.ime              AS korisnik_ime,
                    k.soba             AS soba,
                    z.korisnik_id      AS korisnik_id
                FROM zone z
                LEFT JOIN korisnici k ON z.korisnik_id = k.id
                ORDER BY z.id;
                """
            else:
                q = """
                SELECT 
                    id AS zone_id, naziv AS zone_naziv, alarm_status, last_alarm_time, last_updated, korisnik_id
                FROM zone
                ORDER BY id;
                """
            return pd.read_sql_query(q, conn)
    except Exception as e:
        st.error(f"Greška pri dohvaćanju zona: {e}")
        return pd.DataFrame()


def set_zone_alarm(zone_id: int, on: bool, set_time: bool = True) -> bool:
    """Uključi ili isključi alarm na jednoj zoni."""
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
    """Isključi sve alarme na svim zonama. Vraća broj pogođenih redaka."""
    try:
        ts = now_str()
        with connect() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE zone SET alarm_status = 0, last_updated = ?", (ts,))
            affected = cur.rowcount or 0
            conn.commit()
        return affected
    except Exception as e:
        st.error(f"Greška pri gašenju svih zona: {e}")
        return 0


def random_alarm_on_inactive() -> dict | None:
    """Uključi alarm na jednoj nasumičnoj zoni koja trenutačno nije aktivna."""
    try:
        with connect() as conn:
            df = pd.read_sql_query(
                """
                SELECT id AS zone_id, naziv AS zone_naziv
                FROM zone
                WHERE COALESCE(alarm_status, 0) = 0
                """,
                conn,
            )
        if df.empty:
            return None
        row = df.sample(1).iloc[0]
        zid = int(row["zone_id"])
        ts = now_str()
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE zone
                SET alarm_status = 1,
                    last_alarm_time = ?,
                    last_updated = ?
                WHERE id = ?
                """,
                (ts, ts, zid),
            )
            conn.commit()
        return {"zone_id": zid, "zone_naziv": str(row["zone_naziv"])}
    except Exception as e:
        st.error(f"Greška pri nasumičnom paljenju alarma: {e}")
        return None


def get_osobe_s_aktivnim() -> pd.DataFrame:
    """Popis osoba koje imaju barem jednu zonu u alarmu."""
    try:
        with connect() as conn:
            q = """
            SELECT 
                k.id   AS korisnik_id,
                k.ime  AS korisnik_ime,
                k.soba AS soba,
                COUNT(*) AS broj_aktivnih_zona
            FROM zone z
            JOIN korisnici k ON z.korisnik_id = k.id
            WHERE COALESCE(z.alarm_status, 0) = 1
            GROUP BY k.id, k.ime, k.soba
            ORDER BY broj_aktivnih_zona DESC, k.ime;
            """
            return pd.read_sql_query(q, conn)
    except Exception as e:
        st.error(f"Greška pri dohvaćanju osoba s aktivnim zonama: {e}")
        return pd.DataFrame()


def clear_alarms_by_user(korisnik_id: int) -> int:
    """Gasi sve alarme na zonama koje pripadaju odabranoj osobi. Vraća broj promijenjenih redaka."""
    try:
        ts = now_str()
        with connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE zone
                SET alarm_status = 0,
                    last_updated = ?
                WHERE korisnik_id = ?
                  AND COALESCE(alarm_status, 0) = 1
                """,
                (ts, korisnik_id),
            )
            affected = cur.rowcount or 0
            conn.commit()
        return affected
    except Exception as e:
        st.error(f"Greška pri gašenju alarma po osobi: {e}")
        return 0


def get_aktivni_alarms_zapisi() -> pd.DataFrame:
    """
    Vraća aktivne zapise iz tablice alarms, usklađeno s JSON shemom
    Stupci su id, zone_id, zone_name, vrijeme, potvrda, vrijemePotvrde, korisnik, soba, osoblje
    Aktivnim se smatra zapis bez potvrde ili bez vremena potvrde
    """
    try:
        with connect() as conn:
            chk = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alarms';",
                conn,
            )
            if chk.empty:
                return pd.DataFrame()
            q = """
            SELECT
                a.id                AS alarm_id,
                a.zone_id           AS zone_id,
                a.zone_name         AS zone_naziv,
                a.vrijeme           AS nastao,
                a.potvrda           AS potvrda,
                a.vrijemePotvrde    AS vrijeme_potvrde,
                a.korisnik          AS korisnik,
                a.soba              AS soba,
                a.osoblje           AS osoblje
            FROM alarms a
            WHERE 
                COALESCE(CAST(a.potvrda AS INTEGER), 0) = 0
                OR a.vrijemePotvrde IS NULL
                OR TRIM(COALESCE(a.vrijemePotvrde, '')) = ''
            ORDER BY a.vrijeme DESC, a.id DESC;
            """
            return pd.read_sql_query(q, conn)
    except Exception as e:
        st.error(f"Greška pri dohvaćanju tablice alarms: {e}")
        return pd.DataFrame()


# ------------------ Tabovi ------------------
tab_sim, tab_overview, tab_alarms, tab_by_user, tab_tools = st.tabs(
    [
        "🚨 Simulator",
        "📋 Pregled zona",
        "📡 Aktivni alarmi",
        "👤 Gašenje po osobi",
        "🛠️ Alati",
    ]
)

# ------------------ TAB Simulator ------------------
with tab_sim:
    st.subheader("Generiranje događaja na zonama")

    st.markdown("Nasumični alarm na slobodnoj zoni")
    if st.button("Pokreni nasumični alarm", type="primary", width="stretch"):
        res = random_alarm_on_inactive()
        if res:
            st.success(
                f"Uključen alarm na zoni {res['zone_naziv']} ID {res['zone_id']}"
            )
            st.rerun()
        else:
            st.warning("Nema slobodnih zona ili je došlo do pogreške.")

    st.markdown("---")

    df_zone = get_sve_zone(include_user=True)
    if df_zone.empty:
        st.info("Nema zona za prikaz.")
    else:
        st.markdown("Ručno upravljanje jednom zonom")

        selected_zone_id = st.selectbox(
            "Odaberi zonu",
            options=df_zone["zone_id"].tolist(),
            format_func=lambda zid: f"{df_zone[df_zone['zone_id']==zid]['zone_naziv'].iloc[0]} ID {zid}",
            key="sel_zone",
        )

        if st.button(
            "Uključi alarm na odabranoj zoni", type="primary", width="stretch"
        ):
            if set_zone_alarm(selected_zone_id, on=True, set_time=True):
                st.success("Alarm uključen")
                st.rerun()

        if st.button(
            "Isključi alarm na odabranoj zoni", type="secondary", width="stretch"
        ):
            if set_zone_alarm(selected_zone_id, on=False):
                st.success("Alarm isključen")
                st.rerun()

        st.markdown("Automatsko gašenje nakon isteka vremena")
        secs = st.number_input(
            "Vrijeme do gašenja u sekundama",
            min_value=1,
            max_value=300,
            value=30,
            step=1,
        )
        if st.button("Uključi pa automatski isključi", width="stretch"):
            if set_zone_alarm(selected_zone_id, on=True, set_time=True):
                st.info(f"Uključeno, gašenje za {secs} sekundi.")
                st.toast("Alarm uključen", icon="🔴")
                time.sleep(int(secs))
                set_zone_alarm(selected_zone_id, on=False)
                st.toast("Alarm isključen", icon="🟢")
                st.success("Automatsko gašenje izvršeno")
                st.rerun()

# ------------------ TAB Pregled zona ------------------
with tab_overview:
    st.subheader("Trenutno stanje zona")
    df = get_sve_zone(include_user=True)
    if df.empty:
        st.info("Nema zona za prikaz.")
    else:
        df_view = df.copy()
        df_view["status"] = df_view["alarm_status"].apply(
            lambda v: "🔴 Alarm" if int(v or 0) == 1 else "🟢 U redu"
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
            width="stretch",
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn(format="%d"),
            },
        )

# ------------------ TAB Aktivni alarmi ------------------
with tab_alarms:
    st.subheader("Aktivni alarmi iz tablice alarms")
    df_a = get_aktivni_alarms_zapisi()
    if df_a.empty:
        st.info("Nema aktivnih zapisa ili tablica alarms ne postoji.")
    else:
        df_a_view = df_a.rename(
            columns={
                "alarm_id": "ID alarma",
                "zone_id": "ID zone",
                "zone_naziv": "Zona",
                "nastao": "Vrijeme",
                "potvrda": "Potvrda",
                "vrijeme_potvrde": "Vrijeme potvrde",
                "korisnik": "Korisnik",
                "soba": "Soba",
                "osoblje": "Osoblje",
            }
        )
        st.dataframe(df_a_view, width="stretch", hide_index=True)

# ------------------ TAB Gašenje po osobi ------------------
with tab_by_user:
    st.subheader("Poništenje aktivnih alarma po osobi")
    df_osobe = get_osobe_s_aktivnim()
    if df_osobe.empty:
        st.info("Trenutno nijedna osoba nema aktivne alarme.")
    else:
        prikazi = [
            f"{r.korisnik_ime} soba {r.soba} aktivno {r.broj_aktivnih_zona}"
            for _, r in df_osobe.iterrows()
        ]
        mapa = {
            prikazi[i]: int(df_osobe.iloc[i]["korisnik_id"])
            for i in range(len(prikazi))
        }
        izbor = st.selectbox("Odaberi osobu", options=list(mapa.keys()))
        if st.button("Ugasi sve alarme odabrane osobe", width="stretch"):
            affected = clear_alarms_by_user(mapa[izbor])
            st.success(f"Ugašeno na {affected} zona.")
            st.rerun()

# ------------------ TAB Alati ------------------
with tab_tools:
    st.subheader("Pomoćne radnje i dijagnostika")

    st.markdown("Uključi alarm na više nasumičnih zona")
    n = st.number_input("Broj zona", min_value=1, value=1, step=1)
    if st.button(
        "Uključi alarm na više nasumičnih zona", type="primary", width="stretch"
    ):
        df_all = get_sve_zone(include_user=False)
        if df_all.empty:
            st.error("Nema zona.")
        else:
            df_inactive = df_all[df_all["alarm_status"].fillna(0).astype(int) == 0]
            if df_inactive.empty:
                st.warning("Nema slobodnih zona.")
            else:
                sample = df_inactive.sample(min(int(n), len(df_inactive)))
                ok_cnt = 0
                for _, r in sample.iterrows():
                    ok_cnt += (
                        1
                        if set_zone_alarm(int(r["zone_id"]), on=True, set_time=True)
                        else 0
                    )
                st.success(f"Uključeno na {ok_cnt} zona.")
                st.rerun()

    st.markdown("---")

    st.markdown("Isključi sve zone")
    if st.button("Isključi sve", type="secondary", width="stretch"):
        m = set_all_off()
        st.success(f"Ugašeno na {m} zona.")
        st.rerun()

st.markdown("---")
st.markdown(
    "<sub>Napomena. Simulator mijenja samo tablicu <code>zone</code>. Kiosk iz toga sam stvara zapise u <code>alarms</code>.</sub>",
    unsafe_allow_html=True,
)
