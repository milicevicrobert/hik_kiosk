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
import sqlite3

def insert_or_update_alarm(zona):
    """
    Unesi novi alarm u bazu ako već ne postoji nepotvrđeni alarm za istu zonu.
    Ako alarm već postoji, preskoči unos.

    """
    zone_id = zona.get("id")
    zone_name = zona.get("name")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Provjeri postoji li već nepotvrđen alarm za ovu zonu
        cur.execute("SELECT COUNT(*) FROM alarms WHERE zone_id = ? AND potvrda = 0", (zone_id,))
        already_active = cur.fetchone()[0] > 0

        if already_active:
            return  # preskoči ako već postoji nepotvrđen alarm

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

        print(f"[{datetime.now()}] 🚨 Active alarm: zona {zone_name} (ID {zone_id}), korisnik: {korisnik_ime}, soba: {soba}")


# COMM kontrola
def get_comm_flag(key):
    """
    Dohvati vrijednost zastavice po ključu key iz comm tablice
    """
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM comm WHERE key = ?", (key,))
        row = cur.fetchone()
        return int(row[0]) if row else 0

def set_comm_flag(key, value=0):
    """
    Postavi vrijednost zastavice po ključu key u comm tablici
    """
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
            print(f"[{datetime.now()}] 🔁 Resetiranje alarma na centrali...")
            status, response = clear_axpro_alarms(cookie)
            print(f"[{datetime.now()}] ✅ Resetirano (status: {status})")
            set_comm_flag("resetAlarm", 0)
            return True  # Reset je izvršen
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Greška pri resetiranju alarma: {e}")
            return False  # Reset nije uspješan
    return False  # Nema potrebe za reset

def set_heartbeat():
    """Postavi heartbeat timestamp za monitoring"""
    current_timestamp = int(time.time())
    set_comm_flag("scanner_heartbeat", current_timestamp)

def run_scanner():
    print("✅ AX PRO Scanner pokrenut.")
    print("📡 Pokušavam uspostaviti konekciju s HIKVision AX PRO centralom...")
    
    cookie = None
    connection_attempts = 0
    max_connection_attempts = 5

    while True:
        try:
            # 💓 Postavi heartbeat za monitoring
            set_heartbeat()
            
            # (Re)login ako cookie ne postoji
            if cookie is None:
                connection_attempts += 1
                print(f"🔐 Pokušavam login na centralu... (pokušaj {connection_attempts})")
                
                try:
                    cookie = login_axpro()
                    print("🔑 ✅ Login uspješan! Povezan s AX PRO centralom.")
                    connection_attempts = 0  # Reset counter nakon uspješnog logina
                    
                except Exception as login_error:
                    print(f"❌ Login neuspješan: {login_error}")
                    
                    if connection_attempts >= max_connection_attempts:
                        print(f"⚠️ Previše neuspješnih pokušaja ({max_connection_attempts}). Čekam duže...")
                        time.sleep(30)  # Duža pauza nakon više neuspješnih pokušaja
                        connection_attempts = 0
                    else:
                        time.sleep(5)  # Kratka pauza između pokušaja
                    
                    continue  # Preskoči ostatak petlje i pokušaj ponovno

            # 🔁 Provjeri treba li resetirati alarm
            reset_izvrsen = False
            try:
                reset_izvrsen = resetiraj_alarme_ako_potrebno(cookie)
            except Exception as reset_error:
                print(f"⚠️ Greška pri resetiranju alarma: {reset_error}")

            # 📡 Provjeri statuse zona - SAMO AKO RESET NIJE IZVRŠEN
            
            if not reset_izvrsen:
                try:
                    print("📡 Skeniranje zona...", end="")
                    data = get_zone_status(cookie)
                    zones = data.get("ZoneList", [])
                    print(f" ✅ Pronađeno {len(zones)} zona")

                    active_alarms = 0
                    for entry in zones:
                        zona = entry["Zone"]
                        if zona.get("alarm", False):
                            insert_or_update_alarm(zona)
                            active_alarms += 1

                    if active_alarms > 0:
                        print(f"🚨 Obrađeno {active_alarms} aktivnih alarma")
                    else:
                        print("✅ Nema aktivnih alarma")
                        
                except Exception as scan_error:
                    print(f"❌ Greška pri skeniranju: {scan_error}")
                    # Možda je cookie istekao, resetiraj ga
                    cookie = None
            else:
                print("⏭️ Preskačem skeniranje zona jer je izvršen reset alarma.")
                
        except KeyboardInterrupt:
            print("\n🛑 Scanner zaustavljen od korisnika (Ctrl+C)")
            break
            
        except Exception as e:
            print(f"⚠️ Neočekivana greška: {e}")
            import traceback
            print(f"📋 Detaljnije: {traceback.format_exc()}")
            cookie = None  # prisilni login pri sljedećem krugu

        # Pauza između ciklusa
        print("⏱️ Čekam 2 sekunde do sljedećeg skeniranja...")
        time.sleep(2)

if __name__ == "__main__":
    print("🚀 HIKVision AX PRO Scanner")
    print("=" * 50)
    
    # Provjeri konfiguraciju
    try:
        from axpro_auth import HOST, USERNAME, PASSWORD
        print(f"📋 Konfiguracija:")
        print(f"   AX PRO URL: http://{HOST}")
        print(f"   Username: {USERNAME}")
        print(f"   Password: {'*' * len(PASSWORD)}")
        print(f"   Database: {DB_PATH}")
    except ImportError as e:
        print(f"❌ Greška u konfiguraciji: {e}")
        print("💡 Provjerite postoji li axpro_auth.py s HOST, USERNAME, PASSWORD")
        exit(1)
    
    # Provjeri postoji li baza
    if not os.path.exists(DB_PATH):
        print(f"❌ Baza podataka ne postoji: {DB_PATH}")
        print("💡 Pokrenite init_db.py za kreiranje baze")
        exit(1)
    else:
        print(f"✅ Baza podataka pronađena")
    
    print("=" * 50)
    
    try:
        run_scanner()
    except KeyboardInterrupt:
        print("\n🛑 Scanner zaustavljen.")
    except Exception as e:
        print(f"💥 Kritična greška: {e}")
        import traceback
        traceback.print_exc()
