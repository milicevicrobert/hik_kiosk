"""
alarm_scaner.py je skripta koja kontinuirano skenira AX PRO centralu
za aktivne alarme i ažurira lokalnu SQLite bazu podataka.
Također obrađuje zahtjeve za resetiranje alarma i održava heartbeat za monitoring.

"""

import time
import os
import sqlite3
from ax_config import DB_PATH
from datetime import datetime, timedelta
from axpro_auth import login_axpro, get_zone_status, clear_axpro_alarms

VRIJEME_DO_PONOVNOG_ALARMA = 120  # sekundi (2 min)
TIME_FMT = "%Y-%m-%d %H:%M:%S"


def _parse_ts(ts: str | None) -> datetime | None:
    """Parsira timestamp iz baze u datetime objekt ili None ako nije moguće.
    vraća datetime objekt ili non iz stringa u formatu TIME_FMT"""
    if not ts:
        return None
    try:
        return datetime.strptime(ts, TIME_FMT)
    except Exception:
        return None


def _proslo_dovoljno(last_updated_str: str | None) -> bool:
    """True ako je prošlo barem VRIJEME_DO_PONOVNOG_ALARMA od last_updated."""
    last_upd = _parse_ts(last_updated_str)
    if last_upd is None:
        return True  # ako nemamo podatak, ne koči
    return (datetime.now() - last_upd) >= timedelta(seconds=VRIJEME_DO_PONOVNOG_ALARMA)


def update_zone_status(zona: dict):
    """
    Ažuriraj status zone u tablici zone.
    Ako zona prelazi iz 0 u 1, postavi last_alarm_time, ali SAMO ako je prošlo
    barem VRIJEME_DO_PONOVNOG_ALARMA od zadnjeg last_updated (debounce).
    Poziva se samo za zone koje su u alarmnom stanju.
    """
    zone_id = zona.get("id")
    zone_name = zona.get("name")
    alarm_active = zona.get("alarm", False)
    now = datetime.now().strftime(TIME_FMT)

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # Treba nam i last_updated radi debounce odluke
        cur.execute(
            "SELECT alarm_status, last_updated FROM zone WHERE id = ?", (zone_id,)
        )
        row = cur.fetchone()
        old_status = row[0] if row else 0
        last_updated_db = row[1] if row else None

        if alarm_active:
            if not old_status:
                # Pokušaj prelaza 0 -> 1 uz debounce provjeru
                if _proslo_dovoljno(last_updated_db):
                    cur.execute(
                        """
                        UPDATE zone SET
                            naziv = ?,
                            alarm_status = 1,
                            last_updated = ?,
                            last_alarm_time = ?
                        WHERE id = ?
                        """,
                        (zone_name, now, now, zone_id),
                    )
                    print(
                        f"🔄 Zona {zone_id} ({zone_name}) status: ALARM (debounce OK)"
                    )
                else:
                    # PREVAŽNO: NE diraj last_updated kada blokiraš, jer bi “vječno” prolongirao alarm
                    # eventualno možeš samo ažurirati naziv bez last_updated
                    cur.execute(
                        "UPDATE zone SET naziv = ? WHERE id = ?",
                        (zone_name, zone_id),
                    )
                    print(f"⏳ Zona {zone_id} ({zone_name}) ALARM ignoriran (debounce)")
            else:
                # Već smo u ALARM=1 → samo refresh naziva i last_updated
                cur.execute(
                    """
                    UPDATE zone SET
                        naziv = ?,
                        alarm_status = 1,
                        last_updated = ?
                    WHERE id = ?
                    """,
                    (zone_name, now, zone_id),
                )

        conn.commit()

def get_comm_flag(key: str) -> int:
    """Dohvati vrijednost zastavice po ključu key iz comm tablice"""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM comm WHERE key = ?", (key,))
        row = cur.fetchone()
        return int(row[0]) if row else 0


def set_comm_flag(key: str, value: int = 0):
    """Postavi vrijednost zastavice po ključu key u comm tablici"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO comm (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
            (key, value),
        )
        conn.commit()


def resetiraj_alarme_uvjetno(cookie) -> bool:
    """
    Resetiraj alarme na AX PRO centrali ako je zastavica 'resetAlarm' postavljena na 1.
    Vraća True ako je reset izvršen, False inače.
    """
    if get_comm_flag("resetAlarm") == 1:
        try:
            print("🔁 Resetiranje alarma...")
            status, response = clear_axpro_alarms(cookie)
            set_comm_flag("resetAlarm", 0)
            print("✅ Alarmi resetirani")
            return True
        except Exception as e:
            print(f"❌ Greška resetiranja: {e}")
            return False


def set_heartbeat():
    """Postavi heartbeat timestamp za monitoring"""
    current_timestamp = int(time.time())
    set_comm_flag("scanner_heartbeat", current_timestamp)


def run_scanner():
    print("🚀 AX PRO Scanner pokrenut")
    cookie = None
    connection_attempts = 0
    while True:
        try:
            set_heartbeat()
            if cookie is None:
                # Pokušaj login ako nemamo cookie ako imamo cookie, koristimo postojeći
                connection_attempts += 1
                try:
                    cookie = login_axpro()
                    print("✅ Povezan s AX PRO centralom")
                    connection_attempts = 0
                except Exception as login_error:
                    if connection_attempts >= 5:
                        print(f"❌ Previše neuspješnih pokušaja. Čekam 30s...")
                        time.sleep(30)
                        connection_attempts = 0
                    else:
                        print(f"❌ Login neuspješan ({connection_attempts}/5)")
                        time.sleep(5)
                    continue

            # Ako imamo cookie, nastavljamo s provjerom i skeniranjem
            reset_izvrsen = False
            try:
                reset_izvrsen = resetiraj_alarme_uvjetno(cookie)
            except Exception as reset_error:
                print(f"❌ Greška resetiranja: {reset_error}")

            if not reset_izvrsen:
                try:
                    data = get_zone_status(cookie)
                    zones = data.get("ZoneList", [])

                    for entry in zones:
                        zona = entry["Zone"]
                        # Provjeri je li zona u alarmnom stanju ako jest vraća True inače False
                        if zona.get("alarm", False):
                            # Unesi ili ažuriraj alarm u tablici zona samo ako je u alarmnom stanju
                            update_zone_status(zona)

                except Exception as scan_error:
                    print(f"❌ Greška skeniranja: {scan_error}")
                    cookie = None

        except KeyboardInterrupt:
            print("\n🛑 Scanner zaustavljen")
            break
        except Exception as e:
            print(f"❌ Neočekivana greška: {e}")
            cookie = None

        time.sleep(5)  # Pauza između skeniranja


if __name__ == "__main__":
    print("🚀 HIKVision AX PRO Scanner")
    print("=" * 40)

    try:
        from axpro_auth import HOST, USERNAME, PASSWORD

        print(f"📋 AX PRO: {HOST}, User: {USERNAME}")
        print(f"📋 Database: {DB_PATH}")
    except ImportError as e:
        print(f"❌ Konfiguracija: {e}")
        exit(1)

    if not os.path.exists(DB_PATH):
        print(f"❌ Baza ne postoji: {DB_PATH}")
        exit(1)

    print("=" * 40)

    try:
        run_scanner()
    except KeyboardInterrupt:
        print("\n🛑 Gotovo")
    except Exception as e:
        print(f"💥 Kritična greška: {e}")
