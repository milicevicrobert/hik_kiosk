from nicegui import ui
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# ------------------ CONSTANTS ------------------
DB_PATH = "data/alarmni_sustav.db"  # Path to the SQLite database file
REFRESH_INTERVAL = 2  # seconds - how often to check for new alarms
RENDER_INTERVAL = timedelta(seconds=60)  # Minimum interval between full UI re-renders

# ------------------ HELPER FUNCTIONS ------------------
def get_connection() -> sqlite3.Connection:
    """Create and return a new database connection."""
    return sqlite3.connect(DB_PATH)

def validan_pin(pin: str, duljina: int = 4) -> bool:
    """
    Validate if the PIN is numeric and has the correct length.
    
    Args:
        pin: The PIN string to validate
        duljina: Expected length of the PIN (default 4)
        
    Returns:
        bool: True if PIN is valid, False otherwise
    """
    return pin.isdigit() and len(pin) == duljina

def set_comm_flag(key: str, value: int = 1):
    """
    Set a communication flag in the database (used for inter-process communication).
    
    Args:
        key: The flag key to set
        value: The value to set (default 1)
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO comm (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        conn.commit()

def get_zadnji_potvrdjeni_alarm_korisnika(korisnik: str) -> dict | None:
    """
    Get the last confirmed alarm for a specific user.
    
    Args:
        korisnik: User name to search for
        
    Returns:
        dict: Dictionary containing user, staff, and confirmation time if found
        None: If no confirmed alarm exists for this user
    """
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
    """
    Get all active (unconfirmed) alarms from the database.
    
    Returns:
        pd.DataFrame: DataFrame containing all active alarms
    """
    with get_connection() as conn:
        return pd.read_sql_query("""
            SELECT id, zone_id, zone_name, vrijeme, korisnik, soba
            FROM alarms
            WHERE potvrda = 0
            ORDER BY vrijeme DESC
        """, conn)

def validiraj_osoblje(pin: str) -> tuple | None:
    """
    Validate staff PIN and return staff info if valid.
    
    Args:
        pin: Staff PIN to validate
        
    Returns:
        tuple: (staff_id, staff_name) if PIN is valid
        None: If PIN is invalid or staff is inactive
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, ime
            FROM osoblje
            WHERE sifra = ? AND aktivna = 1
        """, (pin,))
        return cur.fetchone()

def potvrdi_alarm(alarm_id: int, osoblje_ime: str):
    """
    Confirm an alarm in the database.
    
    Args:
        alarm_id: ID of the alarm to confirm
        osoblje_ime: Name of the staff member confirming the alarm
    """
    with get_connection() as conn:
        conn.execute("""
            UPDATE alarms
            SET potvrda = 1,
                osoblje = ?,
                vrijemePotvrde = ?
            WHERE id = ?
        """, (osoblje_ime, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), alarm_id))
        conn.commit()

# ------------------ ALARM DISPLAY CLASS ------------------
class Alarm:
    """Class for displaying and handling individual alarm UI elements."""
    
    def __init__(self, row: dict, container):
        """
        Initialize an Alarm instance.
        
        Args:
            row: Dictionary containing alarm data from database
            container: UI container where this alarm will be displayed
        """
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
            with ui.expansion().classes('border border-gray-300 rounded-xl p-2 w-full') as exp:
                with exp.add_slot('header'):
                    with ui.element('div').classes('grid grid-cols-[2fr_2fr_2fr_3fr] w-full gap-4 px-4'):
                        ui.label(f'🕒 {samo_vrijeme}').classes('text-lg')
                        ui.label(f'⏱️ {proteklo_teksta}').classes('text-lg')
                        ui.label(f'🛏️ {self.soba}').classes('text-lg')
                        ui.label(f'🧓 {self.korisnik}').classes('text-lg')

                # Show last confirmed alarm for this user if available
                zadnji = get_zadnji_potvrdjeni_alarm_korisnika(self.korisnik)
                with ui.row().classes('items-end justify-around w-full gap-4'):
                    if zadnji:
                        try:
                            potvrda_vrijeme = datetime.strptime(zadnji['vrijemePotvrde'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y. %H:%M")
                        except:
                            potvrda_vrijeme = zadnji['vrijemePotvrde']
                        ui.label(f'⏱️{potvrda_vrijeme}, 👩‍⚕️ {zadnji["osoblje"]}, 🚨{self.zone_name.lower()}, 🧓{zadnji["korisnik"]}')\
                            .classes("text-gray-400 text-lg")

                    # PIN input and confirmation button
                    pin_input = ui.input(label='PIN (4 znamenke)', password=True)\
                        .props('type=number inputmode=numeric pattern="[0-9]*"')\
                        .classes('w-60 font-semibold text-2xl')

                    ui.button('POTVRDI', on_click=self._potvrdi(pin_input))\
                        .props('flat unelevated')\
                        .classes('bg-gray-800 rounded-xl text-white hover:bg-gray-700')

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
                set_comm_flag('resetAlarm', 1)
                ui.notify(f'✔️ Alarm potvrđen od: {osoblje[1]}', type='positive')
            else:
                ui.notify('❌ Neispravan PIN ili neaktivno osoblje!', type='negative')
        return handler

# ------------------ SOUND CONTROLLER CLASS ------------------
class AlarmSoundController:
    """Class for managing alarm sound playback."""
    
    def __init__(self, audio_path: str):
        """
        Initialize the sound controller.
        
        Args:
            audio_path: Path to the audio file to play
        """
        self.audio_path = audio_path
        self.enabled = True
        self.audio_element = ui.audio(self.audio_path).props('loop controls=false').classes('hidden')

    def play(self):
        """Play the alarm sound if enabled."""
        if self.enabled:
            ui.run_javascript("document.querySelector('audio')?.play().catch(() => {});")

    def pause(self):
        """Pause the alarm sound."""
        
        ui.run_javascript("document.querySelector('audio')?.pause();")

    def disable(self):
        """Disable sound playback and pause current sound."""
        self.enabled = False
        self.pause()
        ui.notify('🔇 Zvuk isključen', type='info')

    def enable(self):
        """Enable sound playback and notify user."""
        if not self.enabled:
            self.enabled = True
            self.play()
            ui.notify('🔔 Novi alarm – zvuk ponovno uključen', type='warning')

# ------------------ MAIN PAGE ------------------
@ui.page("/")
def main_page():
    """Main application page showing active alarms and controls."""
    last_alarm_ids = set()  # Track displayed alarms to avoid unnecessary updates
    last_render_time = datetime.min  # Track last full render time
    sound = AlarmSoundController('test_alarm.mp3')  # Initialize sound controller

    # Header with current time and title
    with ui.row().classes('items-center justify-between w-full mb-4'):
        current_time_label = ui.label('').classes('text-lg font-mono bg-gray-800 rounded-xl text-white p-2')
        def update_time_label():
            """Update the displayed time label."""
            now = datetime.now()
            current_time_label.text = f' {now.strftime("%d.%m.%Y")} 🕒 {now.strftime("%H:%M")}'
        ui.timer(60.0, update_time_label)  # Update time every minute
        update_time_label()  # Initial update

        ui.label('🔔 AKTIVNI ALARMI - DOM BUZIN sustav nadzora korisnika 🔔').classes(
            'text-center text-lg font-mono bg-gray-800 text-white p-2 rounded-xl font-mono')

        # Sound toggle button
        ui.button('Isključi zvuk', icon='volume_off', on_click=sound.disable)\
            .props('flat unelevated')\
            .classes('bg-gray-800 rounded-xl text-white hover:bg-gray-700')

    # -------------- Container for alarm list ------------------
    alarm_list_container = ui.column().classes('w-full')

    def update_alarms():
        """Check for new alarms and update the UI accordingly."""
        nonlocal last_alarm_ids, last_render_time
        df = get_aktivni_alarms()
        current_ids = set(df["id"].tolist())
        now = datetime.now()
        should_rerender = (not df.empty) and (now - last_render_time >= RENDER_INTERVAL)

        # Skip update if nothing changed and we don't need a periodic re-render
        if df.empty and current_ids == last_alarm_ids:
            return
        if not should_rerender and current_ids == last_alarm_ids:
            return

        last_alarm_ids = current_ids
        last_render_time = now
        alarm_list_container.clear()

        if df.empty:
            # Show idle screen when no alarms are active
            sound.pause()
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
                    ).classes('text-center text-green-900 whitespace-pre-line p-4 text-xl font-bold leading-loose rounded-2xl shadow-2xl')
            
        else:
            # Show all active alarms
            for _, row in df.iterrows():
                Alarm(row, alarm_list_container).prikazi()
            if not sound.enabled:
                sound.enable()
            sound.play()

    # Initial setup
    if not get_aktivni_alarms().empty:
        sound.play()
    else:
        sound.pause()

    update_alarms()  # Initial update
    ui.timer(REFRESH_INTERVAL, update_alarms)  # Set up periodic updates

# ------------------ APPLICATION STARTUP ------------------
ui.run(title="Alarm Kiosk", reload=True, dark=True)