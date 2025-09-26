import os
import sqlite3
from nicegui import ui
from datetime import datetime


# ------------------ CONFIG ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "alarmni_sustav.db")
SOUND_FILE = os.path.join(BASE_DIR, "static", "alarm_3_short.wav")

PIN = int(4)  # broj znamenki PIN-a
TIME_FMT = "%Y-%m-%d %H:%M:%S"
REFRESH_INTERVAL = 5  # sekunde između osvježavanja liste aktivnih alarma




# ------------------ BAZA ------------------
def validiraj_osoblje(pin: str) -> tuple[int, str] | None:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        if len(pin) != PIN or not pin.isdigit():
            return None
        cur.execute(
            """
            SELECT id, ime FROM osoblje
            WHERE sifra = ? AND aktivna = 1""",
            (pin,),
        )
        return cur.fetchone()


def potvrdi_alarm(alarm_id: int, osoblje_ime: str) -> None:
    """Stavi db.alarms.potvrda=1 za zadani alarm_id i zabilježi osoblje_ime i vrijemePotvrde."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE alarms SET
            potvrda = 1, osoblje = ?, vrijemePotvrde = ?
            WHERE id = ?""",
            (osoblje_ime, datetime.now().strftime(TIME_FMT), alarm_id),
        )
        conn.commit()


def reset_zone_alarm(zone_id: int) -> None:
    """Postavi db.zone.alarm_status=0 i last_updated=now() za zadani zone_id."""
    with sqlite3.connect(DB_PATH) as conn:
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


def get_zadnji_potvrdjeni_alarm_korisnika(korisnik: str) -> dict | None:
    """Vrati zadnji potvrđeni alarm za danog korisnika ili None ako nema."""
    if not korisnik:
        return None
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT korisnik, osoblje, vrijemePotvrde
            FROM alarms
            WHERE korisnik = ? AND potvrda = 1 AND vrijemePotvrde IS NOT NULL
            ORDER BY vrijemePotvrde DESC
            LIMIT 1""",
            (korisnik,),
        )
        row = cur.fetchone()
        if row:
            return {"korisnik": row[0], "osoblje": row[1], "vrijemePotvrde": row[2]}
        return None


def get_aktivni_alarmi() -> list[dict]:
    """isčitaj iz db.alarms sve aktivne (potvrda=0) i vrati ih kao listu dict-ova."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, zone_id, zone_name, vrijeme, korisnik, soba
            FROM alarms
            WHERE potvrda = 0
            ORDER BY vrijeme DESC
        """
        ).fetchall()
    return [dict(r) for r in rows]


def check_and_create_alarm_df(DB_PATH: str) -> None:
    """Očitaj sve zone iz db.zone i pripadajuće korisnike
    i za one koje su u alarm_status=1, a nemaju aktivan alarm u db.alarms
    (potvrda=0), dodaj novi red u db.alarms."""
    now_txt = datetime.now().strftime(TIME_FMT)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1) Učitaj sve zone + korisnika
        cur.execute("""
            SELECT z.id, z.naziv, z.korisnik_id, z.alarm_status,
                   k.ime AS korisnik, k.soba
            FROM zone z
            LEFT JOIN korisnici k ON k.id = z.korisnik_id
        """)
        zone_rows = cur.fetchall()

        # 2) Učitaj već aktivne alarme (nepotvrđene)
        cur.execute("SELECT DISTINCT zone_id FROM alarms WHERE potvrda=0")
        aktivni_ids = {row["zone_id"] for row in cur.fetchall()}

        # 3) Filtriraj: zone koje su u alarmu, ali nemaju aktivan alarm
        nove_zone = [
            r for r in zone_rows
            if r["alarm_status"] == 1 and r["id"] not in aktivni_ids
        ]

        if not nove_zone:
            return

        # 4) Bulk INSERT u alarms
        rows = [
            (
                int(r["id"]),
                str(r["naziv"]),
                now_txt,
                0,
                (None if r["korisnik"] is None else str(r["korisnik"])),
                (None if r["soba"] is None else str(r["soba"])),
            )
            for r in nove_zone
        ]
        cur.executemany("""
            INSERT OR IGNORE INTO alarms
                (zone_id, zone_name, vrijeme, potvrda, korisnik, soba)
            VALUES (?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()

# ------------------ AUDIO KONTROLA ------------------


def control_sound(action: str, sound_enabled: bool | None = None) -> bool | None:
    if action == "play":
        ui.run_javascript("window.__playAlarmNow && window.__playAlarmNow();")
    elif action == "pause":
        ui.run_javascript("window.__stopAlarmNow && window.__stopAlarmNow();")
    elif action == "toggle":
        new_state = not sound_enabled
        if new_state:
            ui.run_javascript("window.__playAlarmNow && window.__playAlarmNow();")
            ui.notify("🔊 Zvuk uključen", type="warning")
        else:
            ui.run_javascript("window.__stopAlarmNow && window.__stopAlarmNow();")
            ui.notify("🔇 Zvuk isključen", type="info")
        return new_state
    return sound_enabled


# ------------------ UI KONTROLA ------------------


def prikazi_alarm(row: dict, container, update_callback) -> None:
    alarm_id = row["id"]
    zone_id = row["zone_id"]
    zone_name = row["zone_name"]
    korisnik = row["korisnik"] or "NEPOZNAT"
    soba = row["soba"] or "N/A"
    vrijeme = datetime.strptime(row["vrijeme"], TIME_FMT)

    t_hhmm = vrijeme.strftime("%H:%M")
    proteklo = f"{int((datetime.now() - vrijeme).total_seconds() // 60)} min"

    with container:
        with ui.expansion().classes(
            "max-w-full border border-gray-300 rounded-lg sm:rounded-xl p-1 sm:p-2 w-full"
        ) as exp:
            with exp.add_slot("header"):
                with ui.element("div").classes(
                    "grid grid-cols-[1fr_1fr_3fr_3fr_2fr] sm:grid-cols-[1fr_1fr_1.5fr_1.5fr_1fr] w-full gap-3 px-3"
                ):
                    ui.label(f"🕒 {t_hhmm}")
                    ui.label(f"⏱️ {proteklo}")
                    ui.label(f"🛏️ {soba}").classes("font-bold text-2xl")
                    ui.label(f"🧓 {korisnik}")
                    ui.label(f"🚨 {zone_name}")

            zadnji = get_zadnji_potvrdjeni_alarm_korisnika(korisnik)
            with ui.row().classes("items-end justify-around w-full gap-2 sm:gap-4"):
                if zadnji:
                    try:
                        pv = datetime.strptime(
                            zadnji["vrijemePotvrde"], TIME_FMT
                        ).strftime("%d.%m.%Y. %H:%M")
                    except Exception:
                        pv = zadnji["vrijemePotvrde"]
                    ui.label(
                        f"⏱️{pv}, 👩‍⚕️ {zadnji['osoblje']}, 🚨{zone_name.lower()}, 🧓{zadnji['korisnik']}"
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
                    osoblje = validiraj_osoblje(pin)
                    if not osoblje:
                        ui.notify(
                            "❌ Neispravan PIN ili neaktivno osoblje!", type="negative"
                        )
                        return

                    potvrdi_alarm(alarm_id, osoblje[1])
                    reset_zone_alarm(zone_id)

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
    # skriveni audio element (spreman za autoplay trik)
    ui.audio(SOUND_FILE).props(
        "id=alarm-audio loop controls=false preload=auto autoplay playsinline muted"
    ).classes("hidden")

    # JS helperi: prvo pokušaj preko Fully Kiosk API-ja (nema ograničenja),
    # ako nije dostupan -> HTML5 audio s "muted autoplay -> unmute" trikom.
    ui.run_javascript(
        """
    (function () {

    function playHtml5() {
        const a = document.getElementById('alarm-audio');
        if (!a) return false;

        try {
        a.pause();              // očisti prethodno stanje
        a.currentTime = 0;      // od početka
        a.muted = true;         // start u muted modu (autoplay dopušten)
        const p = a.play();

        // kad krene svirati, odmah ga odmute-aj
        const unmute = () => { try { a.muted = false; } catch(e) {} };
        a.addEventListener('playing', unmute, { once: true });
        // fallback ako 'playing' ne dođe dovoljno brzo
        setTimeout(unmute, 80);

        if (p && typeof p.catch === 'function') p.catch(()=>{});
        return true;
        } catch (e) {
        return false;
        }
    }

    window.__playAlarmNow = () => {
        const a = document.getElementById('alarm-audio');
        const src = a ? (a.currentSrc || a.src) : null;

        // 1) Fully Kiosk Browser (svira bez ikakvog gesta)
        if (typeof fully !== 'undefined' && fully.playSound && src) {
        try { fully.playSound(src); return true; } catch (e) {}
        }

        // 2) HTML5 fallback s muted->unmute
        return playHtml5();
    };

    window.__stopAlarmNow = () => {
        if (typeof fully !== 'undefined' && fully.stopSound) {
        try { fully.stopSound(); } catch (e) {}
        }
        const a = document.getElementById('alarm-audio');
        if (a) { try { a.pause(); } catch(e) {} }
    };

    })();
    """
    )

    last_alarm_ids: set[int] = set()
    sound_paused_by_user = False  # Dodaj varijablu za praćenje pauze
    sound_playing = False

    # --- Siguran UI update: ignorira race nakon gašenja taba/klijenta
    def safe_ui(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (KeyError, RuntimeError):
            # npr. 'Cannot update UI after disconnect' ili već očišćen client
            return

    # header
    with ui.row().classes(
        "max-w-full items-center justify-between w-full mb-3 text-white"
    ):
        time_lbl = ui.label("").classes("bg-gray-800 rounded-lg px-3 py-1")

        def _upd_time():
            """Ažuriraj vrijeme u headeru."""
            now = datetime.now()
            safe_ui(
                setattr,
                time_lbl,
                "text",
                f"{now.strftime('%d.%m.%Y')} 🕒 {now.strftime('%H:%M')}",
            )

        _upd_time()
        clock_timer = ui.timer(60, _upd_time)

        ui.label("🔔 AKTIVNI ALARMI - DOM BUZIN").classes(
            "bg-gray-800 rounded-lg px-3 py-1"
        )

        def pause_sound():
            nonlocal sound_playing, sound_paused_by_user
            control_sound("pause")
            sound_playing = False
            sound_paused_by_user = True
            ui.notify("🔇 Zvuk pauziran", type="info")

        ui.button(icon="volume_off", on_click=pause_sound).props(
            "flat unelevated"
        ).classes("bg-gray-800 rounded-lg text-white hover:bg-gray-700")

    container = ui.column().classes("w-full")
      
    def render_empty():
        safe_ui(container.clear)
        with container:
            with ui.card().classes(
                "flex items-center justify-center w-full mx-auto bg-black"
            ):
                    ui.label(
                    "⚠️ PAŽNJA!\n\n"
                    "Ovaj uređaj je dio sustava za nadzor korisnika.\n"
                    "Namijenjen je isključivo ovlaštenom osoblju doma.\n"
                    "📵 Molimo korisnike, posjetitelje i treće osobe da ne diraju tablet.\n"
                    "Bilo kakva neovlaštena uporaba može uzrokovati prekid rada sustava.\n\n"
                    "Hvala na razumijevanju.\nVaš Dom"
                ).classes(
                    "text-center text-green-900 whitespace-pre-line p-4 text-xl font-bold leading-loose"
                )

    def tick():
        nonlocal last_alarm_ids, sound_playing,sound_paused_by_user

        try:
            check_and_create_alarm_df(DB_PATH)
            rows = get_aktivni_alarmi()
        except Exception as e:
            safe_ui(lambda: ui.notify(f"Greška pri dohvaćanju alarma: {e}", type="warning"))
            if sound_playing:
                control_sound("pause")
                sound_playing = False
            return

        # ako nema aktivnih alarma
        if not rows:
            safe_ui(container.clear)
            render_empty()
            if sound_playing:
                control_sound("pause")
                sound_playing = False
            last_alarm_ids = set()
            sound_paused_by_user = False  # resetiraj kad nema alarma
            return

        # ima aktivnih alarma

        current_ids = {r["id"] for r in rows}
        novi_alarm = not current_ids.issubset(last_alarm_ids)  # True ako postoji novi alarm

        if current_ids != last_alarm_ids:
            safe_ui(container.clear)
            for r in rows:
                prikazi_alarm(r, container, tick)
            last_alarm_ids = current_ids
            if novi_alarm:
                sound_paused_by_user = False  # resetiraj pauzu SAMO ako je došao novi alarm  # resetiraj pauzu kad dođe novi alarm


        if current_ids and not sound_paused_by_user:
            control_sound("play")
            sound_playing = True
        else:
            if sound_playing:
                control_sound("pause")
                sound_playing = False


    ui.timer(REFRESH_INTERVAL, tick)
    ui.timer(1, tick, once=True)  # inicijalni tick nakon 1 sekunde



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
ui.run(title="Alarm Kiosk", reload=True, dark=True, port=8080)
