from nicegui import ui
import sqlite3
import pandas as pd
import time
from datetime import datetime, timedelta
from nice_config import DB_PATH, SOUND_FILE

# ------------------ KONFIG ------------------
REFRESH_INTERVAL = 2  # s: koliko često kiosk "ticka"
COOLDOWN_SECONDS = 120  # s: koliko nakon potvrde NE kreiramo novi alarm za istu zonu
TIME_FMT = "%Y-%m-%d %H:%M:%S"


# helper: pretvori TEXT datum (TIME_FMT) u epoch int
def _to_epoch(text_dt: str | None) -> int:
    """Pretvori TEXT datum (TIME_FMT) u epoch int (broj sekundi od 1.1.1970. u obliku int)."""
    try:
        return int(datetime.strptime(text_dt, TIME_FMT).timestamp()) if text_dt else 0
    except Exception:
        return 0


# ------------------ DB POMOĆNE ------------------


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    # stabilnost sa skenerom (WAL + timeout)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=3000;")
    return conn


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
    set_comm_flag("kiosk_heartbeat", int(time.time()))


# ------------------ ALARM & ZONE LOGIKA ------------------


def create_alarm_from_zone(zone_row: dict) -> None:
    """Unesi novi alarm u tablicu alarms na temelju zone."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO alarms (zone_id, zone_name, vrijeme, potvrda, korisnik, soba)
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (
                zone_row["id"],
                zone_row["naziv"],
                datetime.now().strftime(TIME_FMT),
                zone_row.get("korisnik"),
                zone_row.get("soba"),
            ),
        )
        conn.commit()


def get_aktivni_alarms() -> pd.DataFrame:
    """Vrati sve aktivne alarme iz tablice alarms u bazi podataka."""
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


def validan_pin(pin: str, duljina: int = 4) -> bool:
    return pin.isdigit() and len(pin) == duljina


def validiraj_osoblje(pin: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, ime FROM osoblje
            WHERE sifra = ? AND aktivna = 1
            """,
            (pin,),
        )
        return cur.fetchone()


def potvrdi_alarm(alarm_id: int, osoblje_ime: str):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE alarms SET
                potvrda = 1,
                osoblje = ?,
                vrijemePotvrde = ?
            WHERE id = ?
            """,
            (osoblje_ime, datetime.now().strftime(TIME_FMT), alarm_id),
        )
        conn.commit()


def reset_zone_alarm(zone_id: int):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE zone SET
                alarm_status = 0,
                last_updated = ?
            WHERE id = ?
            """,
            (datetime.now().strftime(TIME_FMT), zone_id),
        )
        conn.commit()


def set_zone_cooldown(zone_id: int, seconds: int = COOLDOWN_SECONDS):
    with get_connection() as conn:
        conn.execute(
            "UPDATE zone SET cooldown_until_epoch = ? WHERE id = ?",
            (int(time.time()) + seconds, zone_id),
        )
        conn.commit()


def get_zadnji_potvrdjeni_alarm_korisnika(korisnik: str) -> dict | None:
    if not korisnik:
        return None
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
            return {"korisnik": row[0], "osoblje": row[1], "vrijemePotvrde": row[2]}
        return None


def check_and_create_alarms():
    """Za svaku zonu u alarmu, ako nema aktivnog alarma i nije u cooldownu – kreiraj novi alarm."""
    now_epoch = int(time.time())
    with get_connection() as conn:
        # dohvatimo sve zone koje su u alarm_status = 1 iz zone tablice u dataframe zones_df
        # i sve aktivne alarme iz alarms tablice u dataframe aktivni_df
        zones_df = pd.read_sql_query(
            """
            SELECT id, naziv, alarm_status, korisnik_id, last_alarm_time,
                   COALESCE(cooldown_until_epoch, 0) AS cooldown_until_epoch
            FROM zone
            """,
            conn,
        )
        aktivni_df = pd.read_sql_query(
            "SELECT zone_id FROM alarms WHERE potvrda = 0",
            conn,
        )
    # aktivni_zone_ids:set zone_id:int koje su u aktivni_df:dataframe
    aktivni_zone_ids = (
        set(aktivni_df["zone_id"].tolist()) if not aktivni_df.empty else set()
    )

    # za svaku zonu u zones_df:dataframe
    for _, row in zones_df.iterrows():
        last_alarm_time_epoch = _to_epoch(row.get("last_alarm_time"))
        cooldown_epoch = int(row.get("cooldown_until_epoch") or 0)
        alarm_status = int(row.get("alarm_status") or 0)
        if alarm_status != 1:
            continue  # zona nije u alarm_status = 1
        if row["id"] in aktivni_zone_ids:
            continue  # već postoji aktivni alarm za tu zonu
        if cooldown_epoch > now_epoch:
            continue  # još traje cooldown nakon potvrde
        if last_alarm_time_epoch <= cooldown_epoch:
            continue  # zadnji stisnuti alarm je za vrijeme zadnjeg cooldowna

        # pokušaj dohvatiti korisnika/sobu prema korisnik_id
        korisnik = None
        soba = None
        kid = row.get("korisnik_id")
        if pd.notna(kid):
            try:
                kid_int = int(kid)
                with get_connection() as conn:
                    kdf = pd.read_sql_query(
                        "SELECT ime, soba FROM korisnici WHERE id = ?",
                        conn,
                        params=(kid_int,),
                    )
                if not kdf.empty:
                    korisnik = kdf.iloc[0]["ime"]
                    soba = kdf.iloc[0]["soba"]
            except Exception:
                pass

        create_alarm_from_zone(
            {
                "id": row["id"],
                "naziv": row["naziv"],
                "korisnik": korisnik,
                "soba": soba,
            }
        )


# ------------------ AUDIO KONTROLA ------------------


def control_sound(action: str, sound_enabled: bool | None = None):
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
        # kad dođe novi alarm, ponovno uključi i pusti
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


# ------------------ UI ELEMENT: PRIKAZ ALARMA ------------------


def prikazi_alarm(row: dict, container, update_callback):
    alarm_id = row["id"]
    zone_id = row["zone_id"]
    zone_name = row["zone_name"]
    korisnik = row["korisnik"] or "NEPOZNAT"
    soba = row["soba"] or "N/A"
    vrijeme = datetime.strptime(row["vrijeme"], TIME_FMT)

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

            zadnji = get_zadnji_potvrdjeni_alarm_korisnika(korisnik)
            with ui.row().classes("items-end justify-around w-full gap-2 sm:gap-4"):
                if zadnji:
                    try:
                        potvrda_vrijeme = datetime.strptime(
                            zadnji["vrijemePotvrde"], TIME_FMT
                        ).strftime("%d.%m.%Y. %H:%M")
                    except Exception:
                        potvrda_vrijeme = zadnji["vrijemePotvrde"]
                    ui.label(
                        f"⏱️{potvrda_vrijeme}, 👩‍⚕️ {zadnji['osoblje']}, 🚨{zone_name.lower()}, 🧓{zadnji['korisnik']}"
                    ).classes("text-gray-400 text-xs sm:text-sm lg:text-base")

                pin_input = (
                    ui.input(label="PIN (4 znamenke)", password=True)
                    .props('type=number inputmode=numeric pattern="[0-9]*"')
                    .classes(
                        "w-40 sm:w-60 font-semibold text-lg sm:text-xl lg:text-2xl"
                    )
                )

                def potvrdi_handler():
                    pin = (pin_input.value or "").strip()
                    if not validan_pin(pin):
                        ui.notify("⚠️ Neispravan PIN!", type="negative")
                        return
                    osoblje = validiraj_osoblje(pin)
                    if not osoblje:
                        ui.notify(
                            "❌ Neispravan PIN ili neaktivno osoblje!", type="negative"
                        )
                        return

                    potvrdi_alarm(alarm_id, osoblje[1])
                    reset_zone_alarm(zone_id)
                    set_zone_cooldown(zone_id, COOLDOWN_SECONDS)

                    # Resetiraj centralu tek kad NEMA više aktivnih alarma
                    with get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT COUNT(*) FROM alarms WHERE potvrda = 0")
                        active_count = cur.fetchone()[0]
                    if int(active_count) == 0:
                        set_comm_flag("resetAlarm", 1)

                    ui.notify(f"✔️ Alarm potvrđen od: {osoblje[1]}", type="positive")
                    if update_callback:
                        update_callback()

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

    # skriveni audio
    ui.audio(SOUND_FILE).props("loop controls=false").classes("hidden")

    # header
    with ui.row().classes(
        "max-w-full items-center justify-between w-full mb-3 text-white"
    ):
        time_lbl = ui.label("").classes("bg-gray-800 rounded-lg px-3 py-1")

        def _upd_time():
            now = datetime.now()
            time_lbl.text = f"{now.strftime('%d.%m.%Y')} 🕒 {now.strftime('%H:%M')}"

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

    def tick():
        nonlocal last_alarm_ids, sound_enabled

        set_kiosk_heartbeat()
        check_and_create_alarms()

        df = get_aktivni_alarms()
        current_ids = set(df["id"].tolist()) if not df.empty else set()

        if not current_ids:
            if last_alarm_ids != current_ids:
                control_sound("pause", sound_enabled)
                render_empty()
            last_alarm_ids = current_ids
            return

        novi_alarm = not current_ids.issubset(last_alarm_ids)
        if current_ids != last_alarm_ids:
            container.clear()
            for _, row in df.iterrows():
                prikazi_alarm(row, container, tick)
            last_alarm_ids = current_ids

        if novi_alarm:
            sound_enabled = control_sound("auto_play", sound_enabled)

    ui.timer(REFRESH_INTERVAL, tick)
    tick()


# ------------------ MOBILE CSS FIXES ------------------
ui.add_head_html(
    """
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<style>
  html { -webkit-text-size-adjust: 100%; -moz-text-size-adjust: 100%; text-size-adjust: 100%; }
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


# ------------------ START ------------------
ui.run(title="Alarm Kiosk", reload=False, dark=True, port=8080)
