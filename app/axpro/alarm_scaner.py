
import time
from ax_config import DB_PATH
from datetime import datetime
from axpro_auth import login_axpro, get_zone_status, clear_axpro_alarms
import sqlite3

def insert_or_update_alarm(zona):
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
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM comm WHERE key = ?", (key,))
        row = cur.fetchone()
        return int(row[0]) if row else 0

def set_comm_flag(key, value=0):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO comm (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        conn.commit()

def resetiraj_alarme_ako_potrebno(cookie):
    if get_comm_flag("resetAlarm") == 1:
        try:
            print(f"[{datetime.now()}] 🔁 Resetiranje alarma na centrali...")
            status, response = clear_axpro_alarms(cookie)
            print(f"[{datetime.now()}] ✅ Resetirano (status: {status})")
            set_comm_flag("resetAlarm", 0)
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Greška pri resetiranju alarma: {e}")

def run_scanner():
    print("✅ Skener pokrenut. Čekam AX PRO...")
    cookie = None

    while True:
        try:
            # (Re)login ako cookie ne postoji
            if cookie is None:
                print("🔐 Pokušavam login na centralu...")
                cookie = login_axpro()
                print("🔑 Login uspješan.")

            # 🔁 Provjeri treba li resetirati alarm
            resetiraj_alarme_ako_potrebno(cookie)

            # 📡 Provjeri statuse zona
            data = get_zone_status(cookie)
            zones = data.get("ZoneList", [])

            for entry in zones:
                zona = entry["Zone"]
                if zona.get("alarm", False):
                    insert_or_update_alarm(zona)

        except Exception as e:
            print(f"⚠️ Greška: {e}")
            cookie = None  # prisilni login pri sljedećem krugu

        time.sleep(2)

if __name__ == "__main__":
   
    run_scanner()
