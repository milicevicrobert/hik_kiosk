"""
alarm_scanner.py
----------------
Kontinuirano čita HIKVISION AX PRO centralu i zrcali stanje u SQLite tablici `zone`.
- Poll svakih 10s (idle), burst nakon promjene (3 brza polla po ~0.5s).
- Odmah nakon uspješnog reseta radi dodatni poll.
- Upsert zona (INSERT ako ne postoji, UPDATE ako postoji).
- last_alarm_time se postavlja SAMO na prijelazu 0->1.
- last_updated se ažurira na svakom čitanju (ping).
- cooldown_until_epoch se resetira kad zona padne 1->0 (podrška kiosku).
- WAL + busy_timeout za stabilan rad paralelno s NiceGUI kioskom.

Ovisnosti:
- ax_config.DB_PATH
- axpro_auth.login_axpro, get_zone_status, clear_axpro_alarms
"""

import os
import time
import random
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from module.config import DB_PATH
from module.axpro_auth import (
    login_axpro,
    get_zone_status,
    clear_axpro_alarms,
    HOST,
    USERNAME,
)

# ------------------ KONFIG ------------------

TIME_FMT = "%Y-%m-%d %H:%M:%S"

POLL_IDLE_SEC = 10  # osnovni poll
POLL_ACTIVE_SEC = 10  # može ostati 10s (želiš štedjeti mrežu)
BURST_POLLS = 3  # broj brzih polla nakon promjene
BURST_SLEEP_SEC = 0.5  # razmak u burstu

LOGIN_MAX_ATTEMPTS = 5
LOGIN_RETRY_SLEEP_SEC = 5
LOGIN_COOLDOWN_AFTER_MAX = 30

BUSY_TIMEOUT_MS = 3000  # SQLite busy timeout
HEARTBEAT_KEY = "scanner_heartbeat"
RESET_FLAG_KEY = "resetAlarm"

# Ako želiš globalni jitter kako se poll ne bi “poklopio” s drugim sustavima:
JITTER_IDLE_SEC = 0.2
JITTER_ACTIVE_SEC = 0.2


# ------------------ DB POMOĆNE ------------------


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    # Stabilnost s paralelnim upisima/čitanjima (kiosk + skener)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS};")
    return conn


def comm_get(key: str, default: int = 0) -> int:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM comm WHERE key = ?", (key,))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else default


def comm_set(key: str, value: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO comm (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()


def set_heartbeat() -> None:
    comm_set(HEARTBEAT_KEY, int(time.time()))


# ------------------ ZONE AŽURIRANJE ------------------


def _now_str() -> str:
    return datetime.now().strftime(TIME_FMT)


def upsert_zone_state(
    zone_id: int, zone_name: str, alarm_active: bool
) -> Tuple[bool, bool]:
    """
    Upsert zone:
    - Ako je prijelaz 0->1: postavi alarm_status=1, last_updated=now i last_alarm_time=now.
    - Ako je 1->1: osvježi last_updated=now (ping).
    - Ako je 1->0: postavi alarm_status=0, last_updated=now i cooldown_until_epoch=0.
    - Ako je 0->0: samo osvježi naziv (nije nužno, ali ostaje dosljedno).

    Vraća (changed, new_status_is_1).
    """
    now = _now_str()
    changed = False
    new_is_1 = bool(alarm_active)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT alarm_status FROM zone WHERE id = ?", (zone_id,))
        row = cur.fetchone()
        old_status = int(row[0]) if row else 0

        if alarm_active:
            if old_status == 0:
                # 0 -> 1
                cur.execute(
                    """
                    UPDATE zone
                    SET naziv=?, alarm_status=1, last_updated=?, last_alarm_time=?
                    WHERE id=?
                    """,
                    (zone_name, now, now, zone_id),
                )
                if cur.rowcount == 0:
                    cur.execute(
                        """
                        INSERT INTO zone (id, naziv, alarm_status, last_updated, last_alarm_time)
                        VALUES (?, ?, 1, ?, ?)
                        """,
                        (zone_id, zone_name, now, now),
                    )
                changed = True
            else:
                # 1 -> 1 (ping + naziv)
                cur.execute(
                    """
                    UPDATE zone
                    SET naziv=?, alarm_status=1, last_updated=?
                    WHERE id=?
                    """,
                    (zone_name, now, zone_id),
                )
        else:
            if old_status == 1:
                # 1 -> 0 (spusti + resetiraj cooldown kioska, ako se koristi)
                cur.execute(
                    """
                    UPDATE zone
                    SET naziv=?, alarm_status=0, last_updated=?, cooldown_until_epoch=0
                    WHERE id=?
                    """,
                    (zone_name, now, zone_id),
                )
                changed = True
            else:
                # 0 -> 0 (osvježi naziv po želji)
                cur.execute(
                    "UPDATE zone SET naziv=? WHERE id=?",
                    (zone_name, zone_id),
                )
                if cur.rowcount == 0:
                    cur.execute(
                        "INSERT INTO zone (id, naziv, alarm_status, last_updated) VALUES (?, ?, 0, ?)",
                        (zone_id, zone_name, now),
                    )

        conn.commit()

    return changed, new_is_1


# ------------------ AX PRO POMOĆNE ------------------


def do_login_with_retries() -> Optional[Any]:
    attempts = 0
    while True:
        try:
            return login_axpro()
        except Exception as e:
            attempts += 1
            print(f"[login] ❌ Neuspjeh ({attempts}/{LOGIN_MAX_ATTEMPTS}): {e}")
            if attempts >= LOGIN_MAX_ATTEMPTS:
                print(f"[login] ⏳ Hladim {LOGIN_COOLDOWN_AFTER_MAX}s...")
                time.sleep(LOGIN_COOLDOWN_AFTER_MAX)
                attempts = 0
            else:
                time.sleep(LOGIN_RETRY_SLEEP_SEC)


def poll_zones(cookie: Any) -> List[Dict[str, Any]]:
    """
    Vraća listu dictova: [{ 'id': int, 'name': str, 'alarm': bool }, ...]
    Oslanja se na axpro_auth.get_zone_status(cookie) -> dict s 'ZoneList'.
    """
    data = get_zone_status(cookie)
    zones = data.get("ZoneList", [])
    out: List[Dict[str, Any]] = []
    for entry in zones:
        z = entry.get("Zone", {})
        # očekuje se da axpro_auth već normalizira polja
        out.append(
            {
                "id": int(z.get("id")),
                "name": str(z.get("name", "")),
                "alarm": bool(z.get("alarm", False)),
            }
        )
    return out


# ------------------ RESET OBRADA ------------------


def process_reset_if_requested(cookie: Any) -> bool:
    """
    Ako je RESET flag postavljen, pokuša resetirati centralu i vratiti flag na 0.
    Vraća True ako je reset odrađen (uspješno pozvan), False inače.
    """
    if comm_get(RESET_FLAG_KEY, 0) != 1:
        return False

    try:
        print("[reset] 🔁 Pokrećem reset na centrali...")
        status, response = clear_axpro_alarms(cookie)
        # status može biti bool ili kod; pretpostavimo da iznimka znači fail
        comm_set(RESET_FLAG_KEY, 0)
        print("[reset] ✅ Reset zatražen i flag vraćen na 0")
        return True
    except Exception as e:
        print(f"[reset] ❌ Greška resetiranja: {e}")
        # flag ostaje 1 pa će se pokušati ponovno u idućem ciklusu
        return False


# ------------------ GLAVNA PETLJA ------------------


def run_scanner() -> None:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Baza ne postoji: {DB_PATH}")

    print("🚀 AX PRO Alarm Scanner")
    print(f"📋 DB: {DB_PATH}")
    cookie: Optional[Any] = None

    while True:
        set_heartbeat()

        # Osiguraj login
        if cookie is None:
            cookie = do_login_with_retries()
            print("[login] ✅ Autoriziran (cookie dobiven)")

        # 1) Reset ako je zatražen
        reset_done = process_reset_if_requested(cookie)
        if reset_done:
            # odmah dodatni poll nakon reseta (ne čekamo interval)
            try:
                zones = poll_zones(cookie)
                changed_any = False
                any_active = False
                for z in zones:
                    changed, is_1 = upsert_zone_state(z["id"], z["name"], z["alarm"])
                    changed_any = changed_any or changed
                    any_active = any_active or is_1
                if changed_any:
                    _do_burst(cookie)
            except Exception as e:
                print(f"[scan] ❌ Greška nakon reseta, ponovno ću se logirati: {e}")
                cookie = None
            # nakon reseta, nastavi uobičajen ciklus spavanja niže

        else:
            # 2) Standardni poll
            try:
                zones = poll_zones(cookie)
                changed_any = False
                any_active = False
                for z in zones:
                    changed, is_1 = upsert_zone_state(z["id"], z["name"], z["alarm"])
                    changed_any = changed_any or changed
                    any_active = any_active or is_1

                if changed_any:
                    _do_burst(cookie)

                # odredi interval (po tvojoj želji oba su 10s)
                interval = POLL_ACTIVE_SEC if any_active else POLL_IDLE_SEC
                # jitter
                interval += random.uniform(
                    -JITTER_ACTIVE_SEC if any_active else -JITTER_IDLE_SEC,
                    JITTER_ACTIVE_SEC if any_active else JITTER_IDLE_SEC,
                )
                if interval < 0.2:
                    interval = 0.2

            except Exception as e:
                print(f"[scan] ❌ Greška skeniranja ({e}), invalidiram cookie...")
                cookie = None
                # blagi backoff da izbjegnemo spam
                interval = 3.0

            time.sleep(interval)


def _do_burst(cookie: Any) -> None:
    """Kratki burst bržih polla nakon promjene stanja kako bi kiosk brže pokupio novost."""
    for i in range(BURST_POLLS):
        try:
            zones = poll_zones(cookie)
            for z in zones:
                upsert_zone_state(z["id"], z["name"], z["alarm"])
        except Exception as e:
            print(f"[burst] ❌ Greška burst polla: {e}")
            break
        time.sleep(BURST_SLEEP_SEC)


# ------------------ MAIN ------------------

if __name__ == "__main__":
    try:
        print("=" * 42)
        print(f"📡 AX PRO: {HOST} (user: {USERNAME})")
        print("=" * 42)
    except Exception:
        pass
    try:
        run_scanner()
    except KeyboardInterrupt:
        print("\n🛑 Zaustavljeno")
    except Exception as e:
        print(f"💥 Kritična greška: {e}")
