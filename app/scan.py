import os
import sqlite3
import pandas as pd
from datetime import datetime
import time
from module.axpro_auth import (
    login_axpro,
    get_zone_status,
    clear_axpro_alarms,
    HOST,
    USERNAME,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "alarmni_sustav.db")
TIME_FMT = "%Y-%m-%d %H:%M:%S"

# ------------------ AXPRO ------------------

SLEEP_TIME_AFTER_RESET = 5  # sekundi nakon reseta centrale
REFRESH_INTERVAL = 10  # sekundi između osvježavanja aktivnih alarma

def poll_zones_df(cookie) -> pd.DataFrame:
    """Uzima cookie od prijave na AXPRO centralu. \n 
    Vrati df: id(int), name(txt), alarm (bool).\n
    za koje "alarm" = 1. Ako nema aktivnih vrati prazan df."""
    data = get_zone_status(cookie)
    zone_list = [z["Zone"] for z in data.get("ZoneList", [])]
    df = pd.DataFrame(zone_list, columns=["id", "name", "alarm"])
    df["alarm"] = df["alarm"].apply(lambda x: int(x) == 1 if x is not None else False)
    #test makni kasnije
    return df[df["alarm"]].reset_index(drop=True)

def sync_active_and_reset(cookie) -> int:
    """Upiše aktivne zone u tablicu db.zone i resetira centralu. Vraća broj upisanih u db.zone."""
    df = poll_zones_df(cookie)
    if df.empty:
        return 0

    now_txt = datetime.now().strftime(TIME_FMT)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # upsert naziva vidi ali je potrebno
        cur.executemany(
            "INSERT INTO zone (id, naziv) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET naziv=excluded.naziv",
            list(df[["id", "name"]].itertuples(index=False, name=None)),
        )

        # postavi aktivno stanje i vremena
        cur.executemany(
            "UPDATE zone SET alarm_status=1, last_alarm_time=? WHERE id=?",
            [(now_txt, int(zid)) for zid in df["id"].tolist()],
        )
        conn.commit()

   
    # reset centrale i kratko pričeka
    try:
        clear_axpro_alarms(cookie)
    except Exception as e:
        print(f"[reset] Upozorenje: {e}")
    time.sleep(SLEEP_TIME_AFTER_RESET)
    return len(df)

# ------------------ GLAVNA PETLJA ------------------


def main():
    cookie = None
    while True:
        try:
            # login ili relogin po potrebi
            if not cookie:
                cookie = login_axpro(HOST, USERNAME)
                if cookie:
                    print("[login] ✅ Autoriziran")
                else:
                    print("[login] ❌ Neuspjela prijava")
                    time.sleep(REFRESH_INTERVAL)
                    continue

            upisano = sync_active_and_reset(cookie)
            if upisano:
                print(f"[scan] ✅ Upisano {upisano} aktivnih zona i resetirana centrala.")
            else:
                print("[scan] — Nema aktivnih zona.")

        except Exception as e:
            print(f"[scan] ❌ Greška: {e}. Pokušavam relogin…")
            cookie = None  # forsiraj novi login
        time.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    main()


