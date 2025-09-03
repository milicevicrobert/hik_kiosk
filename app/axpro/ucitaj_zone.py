import sqlite3
from axpro_auth import login_axpro, get_zone_status
import os
from ax_config import DB_PATH


def ucitaj_zone_iz_centrale():
    try:
        cookie = login_axpro()
        zone_json = get_zone_status(cookie)
        print("📦 JSON s centrale:", zone_json)

        zone_lista = zone_json.get("ZoneList", [])
        return [
            (zona["Zone"]["id"], zona["Zone"]["name"])
            for zona in zone_lista
        ]
    except Exception as e:
        print("❌ Greška pri dohvaćanju zona s centrale:", e)
        return []

def upisi_zone_u_bazu(zone_podaci):
    if not zone_podaci:
        print("⚠️ Nema zona za upis.")
        return

    if not os.path.exists(DB_PATH):
        print("❌ Baza ne postoji:", DB_PATH)
        return

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS zone (id INTEGER PRIMARY KEY, naziv TEXT NOT NULL, korisnik_id INTEGER)")

        nove_zone = 0
        for zona_id, naziv in zone_podaci:
            cur.execute("SELECT 1 FROM zone WHERE id = ?", (zona_id,))
            if not cur.fetchone():
                cur.execute("INSERT INTO zone (id, naziv) VALUES (?, ?)", (zona_id, naziv))
                print(f"✅ Dodana nova zona: {zona_id} – {naziv}")
                nove_zone += 1

        conn.commit()

        if nove_zone == 0:
            print("ℹ️ Sve zone već postoje u bazi.")
        else:
            print(f"🎯 Ukupno dodano novih zona: {nove_zone}")

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"❌ Baza podataka ne postoji: {DB_PATH}")
    else:   
        zone = ucitaj_zone_iz_centrale()
        upisi_zone_u_bazu(zone)
