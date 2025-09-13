from nicegui import ui
import sqlite3
import pandas as pd
import time
from datetime import datetime, timedelta
from nice_config import DB_PATH, SOUND_FILE

# ------------------ CONSTANTS ------------------
REFRESH_INTERVAL = 2
PIN_LENGTH = 4

# ------------------ DATABASE FUNCTIONS ------------------
def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)

def validan_pin(pin: str) -> bool:
    return pin.isdigit() and len(pin) == PIN_LENGTH

def set_kiosk_heartbeat():
    """Postavi heartbeat timestamp za monitoring"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO comm (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, ("kiosk_heartbeat", int(time.time())))
        conn.commit()

def get_zadnji_potvrdjeni_alarm(korisnik: str) -> dict | None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT korisnik, osoblje, vrijemePotvrde FROM alarms
            WHERE korisnik = ? AND potvrda = 1 AND vrijemePotvrde IS NOT NULL
            ORDER BY vrijemePotvrde DESC LIMIT 1
        """, (korisnik,))
        row = cur.fetchone()
        return {"korisnik": row[0], "osoblje": row[1], "vrijemePotvrde": row[2]} if row else None

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
            UPDATE alarms SET potvrda = 1, osoblje = ?, vrijemePotvrde = ?
            WHERE id = ?
        """, (osoblje_ime, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), alarm_id))
        # Set reset flag
        conn.execute("""
            INSERT INTO comm (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, ("resetAlarm", 1))
        conn.commit()

# ------------------ ALARM DISPLAY CLASS ------------------
class Alarm:
    def __init__(self, row: dict, container):

        self.id = row["id"]
        self.zone_name = row["zone_name"]
        self.korisnik = row["korisnik"] or "NEPOZNAT"
        self.soba = row["soba"] or "N/A"
        self.vrijeme = datetime.strptime(row["vrijeme"], "%Y-%m-%d %H:%M:%S")
        self.container = container

    def prikazi(self):
        """Render the alarm UI element."""
        samo_vrijeme = self.vrijeme.strftime("%H:%M")
        proteklo_teksta = f"{int((datetime.now() - self.vrijeme).total_seconds() // 60)} min"

        with self.container:
            with ui.expansion().classes('max-w-full border border-gray-300 rounded-lg sm:rounded-xl p-1 sm:p-2 w-full') as exp:
                with exp.add_slot('header'):
                    with ui.element('div').classes('grid grid-cols-[2fr_2fr_2fr_3fr] sm:grid-cols-[1fr_1fr_1fr_1.5fr] w-full gap-2 sm:gap-4 px-2 sm:px-4'):
                        ui.label(f'🕒 {samo_vrijeme}').classes('text-sm sm:text-base lg:text-lg')
                        ui.label(f'⏱️ {proteklo_teksta}').classes('text-sm sm:text-base lg:text-lg')
                        ui.label(f'🛏️ {self.soba}').classes('text-sm sm:text-base lg:text-lg')
                        ui.label(f'🧓 {self.korisnik}').classes('text-sm sm:text-base lg:text-lg')

                # Show last confirmed alarm for this user if available
                zadnji = get_zadnji_potvrdjeni_alarm(self.korisnik)
                with ui.row().classes('items-end justify-around w-full gap-2 sm:gap-4'):
                    if zadnji:
                        try:
                            potvrda_vrijeme = datetime.strptime(zadnji['vrijemePotvrde'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y. %H:%M")
                        except:
                            potvrda_vrijeme = zadnji['vrijemePotvrde']
                        ui.label(f'⏱️{potvrda_vrijeme}, 👩‍⚕️ {zadnji["osoblje"]}, 🚨{self.zone_name.lower()}')\
                            .classes("text-gray-400 text-xs sm:text-sm lg:text-base")

                    # PIN input and confirmation button
                    pin_input = ui.input(label='PIN (4 znamenke)', password=True)\
                        .props('type=number inputmode=numeric')\
                        .classes('w-40 sm:w-60 font-semibold text-lg sm:text-xl')

                    ui.button('POTVRDI', on_click=self._potvrdi(pin_input))\
                        .classes('bg-gray-800 rounded-lg text-white hover:bg-gray-700')

    def _potvrdi(self, pin_input):
        """Create handler function for alarm confirmation."""
        def handler():
            pin = pin_input.value.strip()
            if not validan_pin(pin):
                ui.notify('⚠️ Neispravan PIN!', type='negative')
                return
            osoblje = validiraj_osoblje(pin)
            if osoblje:
                potvrdi_alarm(self.id, osoblje[1])
                ui.notify(f'✔️ Alarm potvrđen od: {osoblje[1]}', type='positive')
            else:
                ui.notify('❌ Neispravan PIN ili neaktivno osoblje!', type='negative')
        return handler

# ------------------ SOUND CONTROLLER CLASS ------------------
class SoundController:
    def __init__(self, audio_path):
        self.enabled = True
        self.currently_playing = False
        ui.audio(audio_path).props('loop controls=false').classes('hidden')

    def play(self):
        if self.enabled:
            self.currently_playing = True
            ui.run_javascript("document.querySelector('audio')?.play().catch(() => {})")

    def stop(self):
        self.currently_playing = False
        ui.run_javascript("document.querySelector('audio')?.pause()")

    def toggle(self):
        # Toggle služi samo za trenutne alarme - novi alarmi će uvijek aktivirati zvuk
        if self.currently_playing:
            self.stop()
            ui.notify('🔇 Zvuk zaustavljen za trenutne alarme', type='info')
        else:
            self.play()
            ui.notify('� Zvuk uključen', type='positive')

    def play_for_new_alarm(self):
        # Novi alarmi uvijek aktiviraju zvuk bez obzira na trenutno stanje
        self.enabled = True
        self.play()

    def stop_when_no_alarms(self):
        # Zaustavi zvuk kad nema alarma
        self.stop()


# ------------------ MAIN PAGE ------------------
@ui.page("/")
def main_page():
    last_alarm_ids = set()
    sound = SoundController(SOUND_FILE)

    # Header with current time and title
    with ui.row().classes('justify-between items-center w-full mb-4'):
        time_label = ui.label().classes('bg-gray-800 rounded-xl p-2 text-white')
        ui.timer(60, lambda: time_label.set_text(f'{datetime.now().strftime("%d.%m.%Y 🕒 %H:%M")}'))
        
        ui.label('🔔 AKTIVNI ALARMI - DOM BUZIN 🔔').classes('bg-gray-800 p-2 rounded-xl text-white')
        
        ui.button(icon='volume_off', on_click=sound.toggle)\
            .classes('bg-gray-800 text-white hover:bg-gray-700')

    # Container for alarm list
    alarm_container = ui.column().classes('w-full')

    def update_alarms():
        nonlocal last_alarm_ids
        
        set_kiosk_heartbeat()
        df = get_aktivni_alarms()
        current_ids = set(df["id"].tolist())

        # Only update if something changed
        if current_ids == last_alarm_ids:
            return

        # Check for new alarms
        if not current_ids.issubset(last_alarm_ids) and current_ids:
            sound.play_for_new_alarm()
        
        last_alarm_ids = current_ids
        alarm_container.clear()

        if df.empty:
            sound.stop_when_no_alarms()
            with alarm_container:
                with ui.card().classes('w-full h-screen flex items-center justify-center bg-black'):
                    ui.label(
                        '⚠️ PAŽNJA!\n\n'
                        'Ovaj uređaj je dio sustava za nadzor korisnika.\n'
                        'Namijenjen je isključivo ovlaštenom osoblju doma.\n\n'
                        '📵 Molimo ne dirajte tablet.\n\n'
                        'Hvala na razumijevanju.\nVaš Dom'
                    ).classes('text-center text-green-900 whitespace-pre-line p-4 text-xl font-bold')
        else:
            for _, row in df.iterrows():
                Alarm(row, alarm_container).prikazi()

    # Initial setup and timer
    update_alarms()
    ui.timer(REFRESH_INTERVAL, update_alarms)

# ------------------ MOBILE CSS FIXES ------------------
ui.add_head_html('''
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<style>
  html { -webkit-text-size-adjust: 100%; }
  @media screen and (orientation: portrait) and (max-width: 768px) {
    body { transform: rotate(90deg); transform-origin: left top; width: 100vh; height: 100vw; overflow-x: hidden; position: absolute; top: 100%; left: 0; }
  }
</style>
''')

# ------------------ APPLICATION STARTUP ------------------
ui.run(title="Alarm Kiosk", reload=True, dark=True)