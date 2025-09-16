from nicegui import ui
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time
from nice_config import DB_PATH,SOUND_FILE

# ------------------ CONSTANTS ------------------

REFRESH_INTERVAL = 2  # seconds - how often to check for new alarms
RENDER_INTERVAL = timedelta(seconds=60)  # Minimum interval between full UI re-renders

# ------------------ HELPER FUNCTIONS ------------------
def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)

def validan_pin(pin: str, duljina: int = 4) -> bool:
    return pin.isdigit() and len(pin) == duljina

def set_comm_flag(key: str, value: int = 1):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO comm (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        conn.commit()

def set_kiosk_heartbeat():
    """Postavi heartbeat timestamp za monitoring"""
    current_timestamp = int(time.time())
    set_comm_flag("kiosk_heartbeat", current_timestamp)

def get_zadnji_potvrdjeni_alarm_korisnika(korisnik: str) -> dict | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT korisnik, osoblje, vrijemePotvrde
            FROM alarms
            WHERE korisnik = ? AND potvrda = 1 AND vrijemePotvrde IS NOT NULL
            ORDER BY vrijemePotvrde DESC
            LIMIT 1
        """, (korisnik,))
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
        return pd.read_sql_query("""
            SELECT id, zone_id, zone_name, vrijeme, korisnik, soba
            FROM alarms
            WHERE potvrda = 0
            ORDER BY vrijeme DESC
        """, conn)

def validiraj_osoblje(pin: str) -> tuple | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, ime
            FROM osoblje
            WHERE sifra = ? AND aktivna = 1
        """, (pin,))
        return cur.fetchone()

def potvrdi_alarm(alarm_id: int, osoblje_ime: str):
    with get_connection() as conn:
        conn.execute("""
            UPDATE alarms
            SET potvrda = 1,
                osoblje = ?,
                vrijemePotvrde = ?
            WHERE id = ?
        """, (osoblje_ime, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), alarm_id))
        conn.commit()

# ------------------ SOUND CONTROLLER FUNCTIONS ------------------
sound_enabled = True
audio_element = None

def init_sound(audio_path):
    global audio_element
    audio_element = ui.audio(audio_path).props('loop controls=false').classes('hidden')

def play_sound():
    global sound_enabled
    if sound_enabled:
        ui.run_javascript("""
            const audio = document.querySelector('audio');
            if (audio && audio.paused) {
                audio.play().catch(() => {});
            }
        """)

def pause_sound():
    ui.run_javascript("""
        const audio = document.querySelector('audio');
        if (audio && !audio.paused) {
            audio.pause();
        }
    """)

def disable_sound():
    global sound_enabled
    sound_enabled = False
    pause_sound()
    ui.notify('🔇 Zvuk isključen', type='info')

def enable_sound():
    global sound_enabled
    if not sound_enabled:
        sound_enabled = True
        play_sound()
        ui.notify('🔔 Novi alarm – zvuk ponovno uključen', type='warning')

# ------------------ ALARM DISPLAY FUNCTION ------------------
def prikazi_alarm(row: dict, container, update_callback):
    """Prikaži alarm kao UI element."""
    alarm_id = row["id"]
    zone_name = row["zone_name"]
    korisnik = row["korisnik"] or "NEPOZNAT"
    soba = row["soba"] or "N/A"
    vrijeme = datetime.strptime(row["vrijeme"], "%Y-%m-%d %H:%M:%S")
    
    samo_vrijeme = vrijeme.strftime("%H:%M")
    proteklo_teksta = f"{int((datetime.now() - vrijeme).total_seconds() // 60)} min"

    with container:
        with ui.expansion().classes('max-w-full border border-gray-300 rounded-lg sm:rounded-xl p-1 sm:p-2 w-full') as exp:
            with exp.add_slot('header'):
                with ui.element('div').classes('grid grid-cols-[2fr_2fr_2fr_3fr] sm:grid-cols-[1fr_1fr_1fr_1.5fr] w-full gap-2 sm:gap-4 px-2 sm:px-4'):
                    ui.label(f'🕒 {samo_vrijeme}').classes('text-sm sm:text-base lg:text-lg')
                    ui.label(f'⏱️ {proteklo_teksta}').classes('text-sm sm:text-base lg:text-lg')
                    ui.label(f'🛏️ {soba}').classes('text-sm sm:text-base lg:text-lg')
                    ui.label(f'🧓 {korisnik}').classes('text-sm sm:text-base lg:text-lg')

            # Show last confirmed alarm for this user if available
            zadnji = get_zadnji_potvrdjeni_alarm_korisnika(korisnik)
            with ui.row().classes('items-end justify-around w-full gap-2 sm:gap-4'):
                if zadnji:
                    try:
                        potvrda_vrijeme = datetime.strptime(zadnji['vrijemePotvrde'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y. %H:%M")
                    except:
                        potvrda_vrijeme = zadnji['vrijemePotvrde']
                    ui.label(f'⏱️{potvrda_vrijeme}, 👩‍⚕️ {zadnji["osoblje"]}, 🚨{zone_name.lower()}, 🧓{zadnji["korisnik"]}')\
                        .classes("text-gray-400 text-xs sm:text-sm lg:text-base")

                # PIN input and confirmation button
                pin_input = ui.input(label='PIN (4 znamenke)', password=True)\
                    .props('type=number inputmode=numeric pattern="[0-9]*"')\
                    .classes('w-40 sm:w-60 font-semibold text-lg sm:text-xl lg:text-2xl')

                def potvrdi_handler():
                    pin = pin_input.value.strip()
                    if not validan_pin(pin):
                        ui.notify('⚠️ Neispravan PIN!', type='negative')
                        return
                    osoblje = validiraj_osoblje(pin)
                    if osoblje:
                        potvrdi_alarm(alarm_id, osoblje[1])
                        set_comm_flag('resetAlarm', 1)
                        ui.notify(f'✔️ Alarm potvrđen od: {osoblje[1]}', type='positive')
                        # Pozovi update callback za instant refresh
                        if update_callback:
                            update_callback()
                    else:
                        ui.notify('❌ Neispravan PIN ili neaktivno osoblje!', type='negative')

                ui.button('POTVRDI', on_click=potvrdi_handler)\
                    .props('flat unelevated')\
                    .classes('bg-gray-800 rounded-lg sm:rounded-xl text-white hover:bg-gray-700 text-sm sm:text-base')

# ------------------ MAIN PAGE ------------------
@ui.page("/")
def main_page():
    
    last_alarm_ids = set()  # Track displayed alarms to avoid unnecessary updates
    last_render_time = datetime.min  # Track last full render time
    
    # Initialize sound controller
    init_sound(SOUND_FILE)

    # Header with current time and title
    with ui.row().classes('text-sm sm:text-base lg:text-lg max-w-full flex-nowrap font-mono text-white items-center justify-between w-full mb-2 sm:mb-4 whitespace-nowrap'):
        current_time_label = ui.label('').classes('bg-gray-800 rounded-lg sm:rounded-xl p-1 sm:p-2')

        def update_time_label():
            now = datetime.now()
            current_time_label.text = f' {now.strftime("%d.%m.%Y")} 🕒 {now.strftime("%H:%M")}'
        ui.timer(60.0, update_time_label)
        update_time_label()

        ui.label('🔔 AKTIVNI ALARMI - DOM BUZIN sustav nadzora korisnika 🔔').classes(
            'text-center bg-gray-800 p-1 sm:p-2 rounded-lg sm:rounded-xl')

        ui.button( icon='volume_off', on_click=disable_sound)\
            .props('flat unelevated')\
            .classes('bg-gray-800 rounded-lg sm:rounded-xl text-white hover:bg-gray-700')

    # -------------- Container for alarm list ------------------
    alarm_list_container = ui.column().classes('w-full')

    def update_alarms():
        nonlocal last_alarm_ids, last_render_time
        
        # 💓 Postavi heartbeat za monitoring
        set_kiosk_heartbeat()
        
        df = get_aktivni_alarms()
        current_ids = set(df["id"].tolist())
        now = datetime.now()

        # 1. Detektiraj je li došao novi alarm
        novi_alarm = not current_ids.issubset(last_alarm_ids)

        # 2. Nema aktivnih alarma
        if df.empty:
            if current_ids == last_alarm_ids:
                return  # ništa novo, ništa za prikazati

            last_alarm_ids = current_ids
            last_render_time = now
            alarm_list_container.clear()
            pause_sound()

            with alarm_list_container:
                with ui.card().classes('w-full h-screen flex items-center justify-center bg-black'):
                    ui.label(
                        '⚠️ PAŽNJA!\n\n'
                        'Ovaj uređaj je dio sustava za nadzor korisnika.\n'
                        'Namijenjen je isključivo ovlaštenom osoblju doma.\n\n'
                        '📵 Molimo korisnike, posjetitelje i treće osobe:\n'
                        'ne dirajte tablet.\n\n'
                        'Bilo kakva neovlaštena uporaba može uzrokovati\n'
                        'prekid rada sustava.\n\n'
                        'Hvala na razumijevanju.\n'
                        'Vaš Dom'
                    ).classes('text-center text-green-900 whitespace-pre-line p-2 sm:p-4 text-lg sm:text-xl lg:text-2xl font-bold leading-loose rounded-lg sm:rounded-2xl shadow-xl sm:shadow-2xl')
            return

        # 3. Prikaži alarme (ako su novi ili je vrijeme za osvježenje)
        if current_ids != last_alarm_ids or (now - last_render_time >= RENDER_INTERVAL):
            alarm_list_container.clear()
            for _, row in df.iterrows():
                prikazi_alarm(row, alarm_list_container, update_alarms)

            last_render_time = now
            last_alarm_ids = current_ids

            # 4. Pali zvuk SAMO ako je novi alarm
            if novi_alarm:
                if not sound_enabled:
                    enable_sound()
                play_sound()

    # Initial setup
    if not get_aktivni_alarms().empty:
        play_sound()
    else:
        pause_sound()

    update_alarms()  # Initial update
    ui.timer(REFRESH_INTERVAL, update_alarms)  # Set up periodic updates

# ------------------ MOBILE CSS FIXES ------------------
ui.add_head_html('''
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
''')

# ------------------ APPLICATION STARTUP ------------------
ui.run(title="Alarm Kiosk", reload=False, dark=True, port=8080)