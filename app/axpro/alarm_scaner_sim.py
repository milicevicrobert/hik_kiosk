import os
from datetime import datetime
from ax_config import DB_PATH
import sqlite3


def insert_test_alarm(zone_id: int, zone_name: str = None):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # Dohvati ime korisnika, sobu i zone_name iz baze
        cur.execute('''
            SELECT k.ime, k.soba, z.naziv
            FROM zone z
            JOIN korisnici k ON z.korisnik_id = k.id
            WHERE z.id = ?
        ''', (zone_id,))
        korisnik_row = cur.fetchone()
        korisnik_ime = korisnik_row[0] if korisnik_row else "Nepoznat"
        soba = korisnik_row[1] if korisnik_row else None
        if zone_name is None:
            zone_name = korisnik_row[2] if korisnik_row else f"Zona {zone_id}"
        cur.execute('''
            INSERT INTO alarms (zone_id, zone_name, vrijeme, korisnik, soba)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            zone_id,
            zone_name,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            korisnik_ime,
            soba
        ))
        conn.commit()
        print(f"[SIM] 🚨 Test alarm: zona {zone_name} (ID {zone_id}), korisnik: {korisnik_ime}, soba: {soba}")

def run_simulation():
    print("Pokreće se simulacija alarma...")
    while True:
        try:
            zone_id = int(input("Unesi zone_id za test alarm (ili 0 za izlaz): "))
            if zone_id == 0:
                print("Izlaz iz simulacije.")
                break
            insert_test_alarm(zone_id)
        except Exception as e:
            print(f"Greška: {e}")

def print_all_zones():
    """Ispisuje sve zone iz baze, njihove id-ove i povezane korisnike."""
    if not os.path.exists(DB_PATH):
        print(f"Baza podataka ne postoji: {DB_PATH}")
        return
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT z.id, z.naziv, k.ime, k.soba
            FROM zone z
            LEFT JOIN korisnici k ON z.korisnik_id = k.id
            ORDER BY z.id
        ''')
        rows = cur.fetchall()
        if not rows:
            print("Nema zona u bazi.")
            return
        print("Popis zona:")
        for row in rows:
            zone_id, zone_name, korisnik_ime, soba = row
            korisnik_ime = korisnik_ime if korisnik_ime else "Nepoznat"
            soba = soba if soba else "-"
            print(f"ID: {zone_id}, Naziv: {zone_name}, Korisnik: {korisnik_ime}, Soba: {soba}")

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Baza podataka ne postoji: {DB_PATH}")
    else:
        print_all_zones()
        
        print("Pokreće se simulacija alarma...")
        run_simulation()
