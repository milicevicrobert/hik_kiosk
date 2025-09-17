from nicegui import ui
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from nice_config import DB_PATH, SOUND_FILE
import time

# ------------------ CONSTANTS ------------------

with open("head.html", encoding="utf-8") as f:
    HEAD_HTML = f.read()

REFRESH_INTERVAL = 2  # seconds - how often to check for new alarms
RENDER_INTERVAL = timedelta(seconds=60)  # Minimum interval between full UI re-renders


# ------------------ HELPER FUNCTIONS ------------------


def create_alarm_from_zone(zone_row: dict) -> None:
    """Unesi novi alarm u bazu podataka na temelju zone."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO alarms (zone_id, zone_name, vrijeme, potvrda, korisnik, soba)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (
                zone_row["id"],
                zone_row["naziv"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                zone_row.get("korisnik"),  # <-- KORISTI PROSLIJEĐENO
                zone_row.get("soba"),  # <-- KORISTI PROSLIJEĐENO
            ),
        )
        conn.commit()


def check_and_create_alarms():
    """Za svaku zonu s alarm_status=1, ako nema aktivnog alarma, kreiraj novi alarm."""
    with get_connection() as conn:
        # Zone
        zones_df = pd.read_sql_query(
            "SELECT id, naziv, alarm_status, korisnik_id FROM zone", conn
        )

        # Aktivni alarmi (može biti prazno)
        alarms_df = pd.read_sql_query(
            "SELECT zone_id FROM alarms WHERE potvrda = 0", conn
        )
        aktivni_zone_ids = (
            set(alarms_df["zone_id"].tolist()) if not alarms_df.empty else set()
        )

        for _, row in zones_df.iterrows():
            # samo ako je zona u alarmu i nema aktivnog alarma
            if not row.get("alarm_status"):
                continue
            if row["id"] in aktivni_zone_ids:
                continue

            korisnik = None
            soba = None

            # pažljivo pročitaj korisnik_id (može biti NaN)
            kid = row.get("korisnik_id")
            if pd.notna(kid):
                try:
                    kid_int = int(kid)
                    korisnici_df = pd.read_sql_query(
                        "SELECT ime, soba FROM korisnici WHERE id = ?",
                        conn,
                        params=(kid_int,),
                    )
                    if not korisnici_df.empty:
                        korisnik = korisnici_df.iloc[0]["ime"]
                        soba = korisnici_df.iloc[0]["soba"]
                except (TypeError, ValueError):
                    # npr. "NaN" ili nešto nepretvorivo — samo preskoči dohvat korisnika
                    pass

            create_alarm_from_zone(
                {
                    "id": row["id"],
                    "naziv": row["naziv"],
                    "korisnik": korisnik,
                    "soba": soba,
                }
            )
            print(f"🚨 Novi alarm za zonu {row['id']} - {row['naziv']}")


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def reset_zone_alarm(zone_id: int):
    """Spušta zonu u stanje OK: alarm_status=0 i ažurira last_updated."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE zone
            SET alarm_status = 0,
                last_updated = ?
            WHERE id = ?
            """,
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), zone_id),
        )
        conn.commit()


def validan_pin(pin: str, duljina: int = 4) -> bool:
    return pin.isdigit() and len(pin) == duljina


def set_comm_flag(key: str, value: int = 1):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO comm (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
            (key, value),
        )
        conn.commit()


def set_kiosk_heartbeat():
    """Postavi heartbeat timestamp za monitoring"""
    current_timestamp = int(time.time())
    set_comm_flag("kiosk_heartbeat", current_timestamp)


def get_zadnji_potvrdjeni_alarm_korisnika(korisnik: str) -> dict | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT korisnik, osoblje, vrijemePotvrde
            FROM alarms
            WHERE korisnik = ? AND potvrda = 1 AND vrijemePotvrde IS NOT NULL
            ORDER BY vrijemePotvrde DESC
            LIMIT 1
        """,
            (korisnik,),
        )
        row = cur.fetchone()
        if row:
            return {
                "korisnik": row[0],
                "osoblje": row[1],
                "vrijemePotvrde": row[2],
            }
        return None


def get_aktivni_alarms() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT id, zone_id, zone_name, vrijeme, korisnik, soba
            FROM alarms
            WHERE potvrda = 0
            ORDER BY vrijeme DESC
        """,
            conn,
        )


def validiraj_osoblje(pin: str) -> tuple | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, ime
            FROM osoblje
            WHERE sifra = ? AND aktivna = 1
        """,
            (pin,),
        )
        return cur.fetchone()


def potvrdi_alarm(alarm_id: int, osoblje_ime: str):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE alarms
            SET potvrda = 1,
                osoblje = ?,
                vrijemePotvrde = ?
            WHERE id = ?
        """,
            (osoblje_ime, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), alarm_id),
        )
        conn.commit()


# ------------------ SOUND CONTROLLER FUNCTIONS ------------------


def control_sound(action, sound_enabled=None):
    """Jednostavna kontrola zvuka: nema ready/appInitialized flagova."""
    if action == "play" and sound_enabled:
        ui.run_javascript(
            """
            const a = document.querySelector('audio');
            if (a && a.paused) { a.play().catch(()=>{}); }
        """
        )
    elif action == "pause":
        ui.run_javascript(
            """
            const a = document.querySelector('audio');
            if (a && !a.paused) { a.pause(); }
        """
        )
    elif action == "toggle":
        new_state = not sound_enabled
        if new_state:
            ui.run_javascript(
                """
                const a = document.querySelector('audio');
                if (a && a.paused) { a.play().catch(()=>{}); }
            """
            )
            ui.notify("🔊 Zvuk uključen", type="warning")
        else:
            ui.run_javascript(
                """
                const a = document.querySelector('audio');
                if (a && !a.paused) { a.pause(); }
            """
            )
            ui.notify("🔇 Zvuk isključen", type="info")
        return new_state
    elif action == "auto_play":
        # Za novi alarm – ako je bio isključen, uključi, i pusti
        if not sound_enabled:
            ui.notify("🔔 Novi alarm – zvuk ponovno uključen", type="warning")
        ui.run_javascript(
            """
            const a = document.querySelector('audio');
            if (a && a.paused) { a.play().catch(()=>{}); }
        """
        )
        return True
    return sound_enabled


# ------------------ ALARM DISPLAY FUNCTION ------------------
def prikazi_alarm(row: dict, container, update_callback):
    """Prikaži alarm kao UI element."""
    alarm_id = row["id"]
    zone_id = row["zone_id"]
    zone_name = row["zone_name"]
    korisnik = row["korisnik"] or "NEPOZNAT"
    soba = row["soba"] or "N/A"
    vrijeme = datetime.strptime(row["vrijeme"], "%Y-%m-%d %H:%M:%S")

    samo_vrijeme = vrijeme.strftime("%H:%M")
    proteklo_teksta = f"{int((datetime.now() - vrijeme).total_seconds() // 60)} min"

    with container:
        with ui.expansion().classes(
            "max-w-full border border-gray-300 rounded-lg sm:rounded-xl p-1 sm:p-2 w-full"
        ) as exp:
            with exp.add_slot("header"):
                with ui.element("div").classes(
                    "grid grid-cols-[2fr_2fr_2fr_3fr] sm:grid-cols-[1fr_1fr_1fr_1.5fr] w-full gap-2 sm:gap-4 px-2 sm:px-4"
                ):
                    ui.label(f"🕒 {samo_vrijeme}").classes(
                        "text-sm sm:text-base lg:text-lg"
                    )
                    ui.label(f"⏱️ {proteklo_teksta}").classes(
                        "text-sm sm:text-base lg:text-lg"
                    )
                    ui.label(f"🛏️ {soba}").classes("text-sm sm:text-base lg:text-lg")
                    ui.label(f"🧓 {korisnik}").classes(
                        "text-sm sm:text-base lg:text-lg"
                    )

            # Show last confirmed alarm for this user if available
            zadnji = get_zadnji_potvrdjeni_alarm_korisnika(korisnik)
            with ui.row().classes("items-end justify-around w-full gap-2 sm:gap-4"):
                if zadnji:
                    try:
                        potvrda_vrijeme = datetime.strptime(
                            zadnji["vrijemePotvrde"], "%Y-%m-%d %H:%M:%S"
                        ).strftime("%d.%m.%Y. %H:%M")
                    except:
                        potvrda_vrijeme = zadnji["vrijemePotvrde"]
                    ui.label(
                        f'⏱️{potvrda_vrijeme}, 👩‍⚕️ {zadnji["osoblje"]}, 🚨{zone_name.lower()}, 🧓{zadnji["korisnik"]}'
                    ).classes("text-gray-400 text-xs sm:text-sm lg:text-base")

                # PIN input and confirmation button
                pin_input = (
                    ui.input(label="PIN (4 znamenke)", password=True)
                    .props('type=number inputmode=numeric pattern="[0-9]*"')
                    .classes(
                        "w-40 sm:w-60 font-semibold text-lg sm:text-xl lg:text-2xl"
                    )
                )

                def potvrdi_handler():
                    """
                    Handler za potvrdu alarma.
                    1) Validira PIN i osoblje
                    2) Označi alarm potvrđenim
                    3) (DODANO) Spusti zonu: alarm_status=0, last_updated=NOW
                    4) (opcionalno) postavi comm flag za stvarni reset centrale
                    5) Refresh UI
                    """
                    # 1) Validira PIN i osoblje
                    pin = pin_input.value.strip()
                    if not validan_pin(pin):
                        ui.notify("⚠️ Neispravan PIN!", type="negative")
                        return
                    osoblje = validiraj_osoblje(pin)
                    if not osoblje:
                        ui.notify(
                            "❌ Neispravan PIN ili neaktivno osoblje!", type="negative"
                        )
                        return

                    # 2) Označi alarm potvrđenim
                    potvrdi_alarm(alarm_id, osoblje[1])
                    # 3) Spusti zonu u stanje OK
                    reset_zone_alarm(zone_id)
                    # 4) Postavi comm flag za reset centrale
                    set_comm_flag("resetAlarm", 1)

                    ui.notify(f"✔️ Alarm potvrđen od: {osoblje[1]}", type="positive")
                    # 5) Refresh UI
                    if update_callback:
                        update_callback()

                # Pin input enter key triggers confirmation
                ui.button("POTVRDI", on_click=potvrdi_handler).props(
                    "flat unelevated"
                ).classes(
                    "bg-gray-800 rounded-lg sm:rounded-xl text-white hover:bg-gray-700 text-sm sm:text-base"
                )


# ------------------ MAIN PAGE ------------------
@ui.page("/")
def main_page():
    last_alarm_ids: set[int] = set()
    sound_enabled = True

    # Skriveni audio (pretpostavljaš da je SOUND_FILE definiran)
    ui.audio(SOUND_FILE).props("loop controls=false").classes("hidden")

    # Header (sat + naslov + mute)
    with ui.row().classes(
        "max-w-full items-center justify-between w-full mb-3 text-white"
    ):
        time_lbl = ui.label("").classes("bg-gray-800 rounded-lg px-3 py-1")

        def _upd_time():
            from datetime import datetime

            now = datetime.now()
            time_lbl.text = f'{now.strftime("%d.%m.%Y")} 🕒 {now.strftime("%H:%M")}'

        _upd_time()
        ui.timer(60, _upd_time)

        ui.label("🔔 AKTIVNI ALARMI - DOM BUZIN").classes(
            "bg-gray-800 rounded-lg px-3 py-1"
        )

        def _toggle_sound():
            nonlocal sound_enabled
            sound_enabled = control_sound("toggle", sound_enabled)

        ui.button(icon="volume_off", on_click=_toggle_sound).props(
            "flat unelevated"
        ).classes("bg-gray-800 rounded-lg text-white hover:bg-gray-700")

    # Glavni kontejner za listu alarma
    container = ui.column().classes("w-full")

    def render_empty():
        container.clear()
        with container:
            with ui.card().classes(
                "w-full h-screen flex items-center justify-center bg-black"
            ):
                ui.label(
                    "⚠️ PAŽNJA!\n\n"
                    "Ovaj uređaj je dio sustava za nadzor korisnika.\n"
                    "Namijenjen je isključivo ovlaštenom osoblju doma.\n\n"
                    "📵 Molimo korisnike, posjetitelje i treće osobe: ne dirajte tablet.\n\n"
                    "Bilo kakva neovlaštena uporaba može uzrokovati prekid rada sustava.\n\n"
                    "Hvala na razumijevanju.\nVaš Dom"
                ).classes(
                    "text-center text-green-900 whitespace-pre-line p-4 text-xl font-bold leading-loose"
                )

    # Jedan “tick” koji radi sve
    def tick():
        nonlocal last_alarm_ids, sound_enabled

        # 1) heartbeat + kreiraj alarme iz zona
        set_kiosk_heartbeat()
        check_and_create_alarms()

        # 2) učitaj aktivne alarme
        df = get_aktivni_alarms()
        current_ids = set(df["id"].tolist()) if not df.empty else set()

        # 3) prikaži
        if not current_ids:
            # nema aktivnih → pauziraj zvuk + prazan ekran ako je promjena
            if last_alarm_ids != current_ids:
                control_sound("pause", sound_enabled)
                render_empty()
            last_alarm_ids = current_ids
            return

        # ima aktivnih → re-render samo kad se promijenilo
        novi_alarm = not current_ids.issubset(last_alarm_ids)
        if current_ids != last_alarm_ids:
            container.clear()
            for _, row in df.iterrows():
                prikazi_alarm(row, container, tick)  # koristi tvoju postojeću funkciju
            last_alarm_ids = current_ids

        # 4) zvuk: pusti samo kad je došao novi
        if novi_alarm:
            sound_enabled = control_sound("auto_play", sound_enabled)

    # Jedan jedini periodički timer
    ui.timer(REFRESH_INTERVAL, tick)

    # inicijalni prikaz odmah
    tick()


# ------------------ MOBILE CSS FIXES ------------------
ui.add_head_html(
    """
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<style>
  /* Disable automatic font scaling in mobile browsers */
  html {
    -webkit-text-size-adjust: 100%;
    -moz-text-size-adjust: 100%;
    text-size-adjust: 100%;
  }
  
  /* Force landscape orientation on mobile devices */
  @media screen and (orientation: portrait) and (max-width: 768px) {
    body {
      transform: rotate(90deg);
      transform-origin: left top;
      width: 100vh;
      height: 100vw;
      overflow-x: hidden;
      position: absolute;
      top: 100%;
      left: 0;
    }
  }
</style>
"""
)


# ------------------ APPLICATION STARTUP ------------------
ui.run(title="Alarm Kiosk", reload=False, dark=True, port=8080)
