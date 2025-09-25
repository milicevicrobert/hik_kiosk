import os
import sqlite3
from nicegui import ui
import pandas as pd
from datetime import datetime
import time
from module.config import DB_PATH, TIME_FMT, PIN
from module.axpro_auth import (
    login_axpro,
    get_zone_status,
    clear_axpro_alarms,
    HOST,
    USERNAME,
)

# ------------------ CONFIG ------------------

SOUND_FILE = os.path.join(
    os.path.dirname(__file__), "test_alarm.mp3"
)  # putanja do audio fajla za alarm


# ------------------ AXPRO ------------------

SLEEP_TIME_AFTER_RESET = 5  # sekundi nakon reseta centrale
REFRESH_INTERVAL = 10  # sekundi između osvježavanja aktivnih alarma


def poll_zones_df(cookie) -> pd.DataFrame:
    """Vrati DataFrame zona s poljima: id(int), name(txt), alarm (bool).\n
    Vrati samo zone koje su u alarm stanju "alarm" = 1. Ako nema, vrati prazan DF."""
    data = get_zone_status(cookie)
    zone_list = [z["Zone"] for z in data.get("ZoneList", [])]
    df = pd.DataFrame(zone_list, columns=["id", "name", "alarm"])
    df["alarm"] = df["alarm"].apply(lambda x: int(x) == 1 if x is not None else False)
    #test makni kasnije
    print(df)
    return df[df["alarm"]].reset_index(drop=True)


def sync_active_and_reset() -> int:
    """Upiše aktivne zone u tablicu zone i resetira centralu. Vraća broj upisanih."""
    try:
        cookie = login_axpro(HOST, USERNAME)
    except Exception as e:
        print(f"Greška pri prijavi na Axpro centralu: {e}")
        return 0

    df = poll_zones_df(cookie)
    if df.empty:
        print("Nema aktivnih zona za upis.")
        return 0
    now_txt = datetime.now().strftime(TIME_FMT)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # upsert naziva vidi ali je potrebno
        cur.executemany(
            "INSERT INTO zone (id, naziv) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET naziv=excluded.naziv",
            list(df[["id", "name"]].itertuples(index=False, name=None)),
        )

        # postavi aktivno stanje i vremena
        cur.executemany(
            "UPDATE zone SET alarm_status=1, last_alarm_time=? WHERE id=?",
            [(now_txt, int(zid)) for zid in df["id"].tolist()],
        )
        conn.commit()

    # resetiraj centralu nakon upisa
    clear_axpro_alarms(cookie)
    # pričekaj da se centrala resetira 5 secundi
    time.sleep(SLEEP_TIME_AFTER_RESET)
    return len(df)


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
    now_txt = datetime.now().strftime(TIME_FMT)
    with sqlite3.connect(DB_PATH) as conn:
        # 1) Učitaj potrebne tablice u DF-ove
        df_zone = pd.read_sql_query(
            """
            SELECT z.id, z.naziv, z.korisnik_id, z.alarm_status,
                   k.ime AS korisnik, k.soba
            FROM zone z
            LEFT JOIN korisnici k ON k.id = z.korisnik_id
        """,
            conn,
        )
        df_aktivni = pd.read_sql_query(
            "SELECT DISTINCT zone_id FROM alarms WHERE potvrda=0", conn
        )
        # 2) Filtriraj: samo zone u alarmu bez već aktivnog alarma
        df = df_zone[df_zone["alarm_status"] == 1].copy()
        if not df_aktivni.empty:
            df = df.merge(df_aktivni, how="left", left_on="id", right_on="zone_id")
            df = df[df["zone_id"].isna()]  # anti-join
            df = df.drop(columns=["zone_id"])
        if df.empty:
            return
        # 3) Bulk INSERT u alarms (jedna transakcija)
        rows = [
            (
                int(r.id),
                str(r.naziv),
                now_txt,
                0,
                (None if pd.isna(r.korisnik) else str(r.korisnik)),
                (None if pd.isna(r.soba) else str(r.soba)),
            )
            for r in df[["id", "naziv", "korisnik", "soba"]].itertuples(index=False)
        ]
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT OR IGNORE INTO alarms
                (zone_id, zone_name, vrijeme, potvrda, korisnik, soba)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            rows,
        )
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
                    "grid grid-cols-[2fr_2fr_2fr_3fr] sm:grid-cols-[1fr_1fr_1fr_1.5fr] w-full gap-3 px-3"
                ):
                    ui.label(f"🕒 {t_hhmm}")
                    ui.label(f"⏱️ {proteklo}")
                    ui.label(f"🛏️ {soba}")
                    ui.label(f"🧓 {korisnik}")

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
    sound_enabled = True

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

        def _toggle_sound():
            nonlocal sound_enabled
            sound_enabled = control_sound("toggle", sound_enabled)

        ui.button(icon="volume_off", on_click=_toggle_sound).props(
            "flat unelevated"
        ).classes("bg-gray-800 rounded-lg text-white hover:bg-gray-700")

    container = ui.column().classes("w-full")

    def render_empty():
        safe_ui(container.clear)
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
        # 1) Sinkroniziraj aktivne zone i resetiraj centralu
        try:
            upisano = sync_active_and_reset()
            upisano = 0
        except Exception as e:
            print(f"Greška pri sinkronizaciji s centralom: {e}")
            upisano = 0
        if upisano:
            print(f"Upisano {upisano} novih aktivnih zona u bazu.")
        # 2) Provjeri i kreiraj nove zapise u alarms
        check_and_create_alarm_df(DB_PATH)
        # 3) Učitaj aktivne alarme i prikaži ih

        rows = get_aktivni_alarmi() or []
        current_ids = {r["id"] for r in rows}

        if not current_ids:
            if last_alarm_ids != current_ids:
                control_sound("pause")
                render_empty()
            last_alarm_ids = current_ids
            return

        if current_ids != last_alarm_ids:
            safe_ui(container.clear)
            for row in rows:
                prikazi_alarm(row, container, tick)
            last_alarm_ids = current_ids

        if sound_enabled:
            control_sound("play")

    main_timer = ui.timer(REFRESH_INTERVAL, tick)
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
