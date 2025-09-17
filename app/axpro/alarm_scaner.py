"""
alarm_scaner.py je aplikacija koja kontinuirano skenira AX PRO centralu za aktivne alarme.
Kada se detektira novi alarm, on se unosi u lokalnu SQLite bazu podataka.
Također, aplikacija može resetirati alarme na centrali ako je to zatraženo putem baze podataka.

Način resetiranja alarma:
1. Postavite vrijednost 'resetAlarm' u tablici 'comm' na 1.
2. Aplikacija će detektirati ovu promjenu i poslati naredbu za resetiranje alarma na AX PRO centralu.
3. Nakon uspješnog resetiranja, vrijednost 'resetAlarm' će biti postavljena natrag na 0.

Ova aplikacija koristi funkcije iz modula axpro_auth.py za autentifikaciju i dohvat statusa zona.
Također koristi SQLite za pohranu i upravljanje alarmima.

Autor: Robert Miličević"""


import time
import os
import sqlite3
from ax_config import DB_PATH
from datetime import datetime
from axpro_auth import login_axpro, get_zone_status, clear_axpro_alarms

GRACE_PERIOD_MINUTES = 1  # Grace period za potvrđene alarme

def insert_or_update_alarm(zona):
    """
    Unesi novi alarm u bazu ako već ne postoji nepotvrđeni alarm za istu zonu.
    Ako alarm već postoji, preskoči unos.
    """
    zone_id = zona.get("id")
    zone_name = zona.get("name")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Provjeri postoji li već nepotvrđen alarm za ovu zonu ili potvrđen unutar grace perioda
        cur.execute("""
            SELECT COUNT(*) FROM alarms 
            WHERE zone_id = ? 
            AND (potvrda = 0 OR 
                (potvrda = 1 AND datetime(vrijemePotvrde) > datetime('now', '-{} minutes')))
        """.format(GRACE_PERIOD_MINUTES), (zone_id,))
        recent_alarm = cur.fetchone()[0] > 0

        if recent_alarm:
            return  # preskoči ako već postoji nepotvrđen alarm ili potvrđen unutar grace perioda

        # Dohvati ime korisnika i sobu iz zone
        cur.execute("""
            SELECT k.ime, k.soba
            FROM zone z
            JOIN korisnici k ON z.korisnik_id = k.id
            WHERE z.id = ?
        """, (zone_id,))
        korisnik_row = cur.fetchone()
        korisnik_ime = korisnik_row[0] if korisnik_row else "Nepoznat"
        soba = korisnik_row[1] if korisnik_row else None

        # Unesi novi alarm s poljem 'soba'
        cur.execute("""
            INSERT INTO alarms (zone_id, zone_name, vrijeme, korisnik, soba)
            VALUES (?, ?, ?, ?, ?)
        """, (
            zone_id,
            zone_name,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            korisnik_ime,
            soba
        ))
        conn.commit()

        print(f"🚨 NOVI ALARM: {korisnik_ime} ({zone_name}), soba: {soba}")


def get_comm_flag(key):
    """Dohvati vrijednost zastavice po ključu key iz comm tablice"""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM comm WHERE key = ?", (key,))
        row = cur.fetchone()
        return int(row[0]) if row else 0

def set_comm_flag(key, value=0):
    """Postavi vrijednost zastavice po ključu key u comm tablici"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO comm (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        conn.commit()

def resetiraj_alarme_ako_potrebno(cookie):
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

            reset_izvrsen = False
            try:
                reset_izvrsen = resetiraj_alarme_ako_potrebno(cookie)
            except Exception as reset_error:
                print(f"❌ Greška resetiranja: {reset_error}")

            if not reset_izvrsen:
                try:
                    data = get_zone_status(cookie)
                    zones = data.get("ZoneList", [])

                    active_alarms = 0
                    for entry in zones:
                        zona = entry["Zone"]
                        if zona.get("alarm", False):
                            insert_or_update_alarm(zona)
                            active_alarms += 1

                    #if active_alarms > 0:
                    #    print(f"🚨 Obrađeno {active_alarms} alarma")
                        
                except Exception as scan_error:
                    print(f"❌ Greška skeniranja: {scan_error}")
                    cookie = None
                
        except KeyboardInterrupt:
            print("\n🛑 Scanner zaustavljen")
            break
        except Exception as e:
            print(f"❌ Neočekivana greška: {e}")
            cookie = None

        time.sleep(2)

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