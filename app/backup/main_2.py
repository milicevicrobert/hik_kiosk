from nicegui import ui
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import time

# ------------------ KONSTANTE ------------------
DB_PATH = "data/alarmni_sustav.db"
REFRESH_INTERVAL = 2  # sekunde

# ------------------ HELPER FUNKCIJE ------------------


def get_connection() -> sqlite3.Connection:
    """Stvara i vraća novu konekciju na SQLite bazu podataka."""
    return sqlite3.connect(DB_PATH)


def validan_pin(pin: str, duljina: int = 4) -> bool:
    """
    Provjerava je li uneseni PIN ispravan:
    - sadrži točno 'duljina' znamenki
    - sastoji se samo od brojeva
    """
    return pin.isdigit() and len(pin) == duljina


def set_comm_flag(key: str, value: int = 1) -> None:
    """
    Postavlja (ili ažurira) komunikacijsku zastavicu u tablici 'comm'.
    Ako ključ već postoji, vrijednost se ažurira.
    Primjer: set_comm_flag('resetAlarm', 1)
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO comm (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        conn.commit()


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
    """
    Vraća DataFrame s aktivnim (nepotvrđenim) alarmima iz baze.
    Alarmi su sortirani po vremenu unazad.
    """
    with get_connection() as conn:
        return pd.read_sql_query("""
            SELECT id, zone_id, zone_name, vrijeme, korisnik, soba
            FROM alarms
            WHERE potvrda = 0
            ORDER BY vrijeme DESC
        """, conn)


def validiraj_osoblje(pin: str) :
    """
    Provjerava postoji li aktivno osoblje sa zadanom šifrom (PIN-om).
    Ako postoji, vraća (id, ime), inače vraća None.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, ime
            FROM osoblje
            WHERE sifra = ? AND aktivna = 1
        """, (pin,))
        return cur.fetchone()


def potvrdi_alarm(alarm_id: int, osoblje_ime: str) -> None:
    """
    Označava alarm kao potvrđen u bazi:
    - postavlja potvrdu na 1
    - sprema ime osoblja koje je potvrdilo
    - sprema vrijeme potvrde (trenutno vrijeme)
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


# ------------------ Main page ------------------

@ui.page("/")
def main_page():
    
    # Ovo prati kad je zadnji put stranica renderirana
    last_render_time = datetime.min
    RENDER_INTERVAL = timedelta(seconds=60)
   
   # Početak stranice
    def disable_sound() -> None:
        """Onemogućuje zvuk i pauzira audio player."""
        nonlocal sound_enabled
        sound_enabled = False
        ui.run_javascript("document.querySelector('audio')?.pause();")
        ui.notify('🔇 Zvuk isključen', type='info')

    with ui.row().classes('items-center justify-between w-full mb-4'):
        current_time_label = ui.label('').classes('text-lg font-mono bg-gray-800 rounded-xl text-white p-2')
        def update_time_label():
            now = datetime.now()
            current_time_label.text = f' {now.strftime("%d.%m.%Y")} 🕒 {now.strftime("%H:%M")}'
        # Osvježava svake 60 sekundi
        ui.timer(60.0, update_time_label)
        update_time_label()  # pozovi odmah da se prvi prikaz ne čeka

        ui.label('🔔 AKTIVNI ALARMI - DOM BUZIN sustav nadzora korisnika 🔔').classes('text-center text-lg font-mono bg-gray-800 text-white p-2 rounded-xl font-mono')
        sound_button = ui.button('Isključi zvuk', icon='volume_off', on_click=disable_sound)\
            .props('flat unelevated')\
            .classes('bg-gray-800 rounded-xl text-white hover:bg-gray-700')

        
    # Container for alarms
    alarms_container = ui.column().classes('w-full')
    last_alarm_ids = set()
    
    # Audio control
    audio_element = ui.audio('test_alarm.mp3').props('loop controls=false').classes('hidden')
    sound_enabled = True
    
    
    def update_alarms() -> None:
        """
        Ažurira prikaz aktivnih alarma u sučelju.

        Funkcionalnosti:
        - Dohvaća sve trenutno aktivne alarme iz baze (gdje potvrda = 0)
        - Ako je došlo do promjene u listi alarma (po ID-u):
            - Briše prethodni prikaz
            - Prikazuje nove alarme kao interaktivne kartice
            - Omogućuje unos PIN-a za potvrdu svakog alarma
            - Pokreće ili pauzira zvučni alarm ovisno o stanju
        - Ako korisnik prethodno isključi zvuk (sound_enabled = False),
        a pojavi se novi alarm, zvuk se automatski ponovno uključuje.
        - Gumb za zvuk vizualno se ažurira ako se stanje zvuka promijeni.

        Napomena:
        Funkcija koristi 'nonlocal' varijable iz konteksta glavne stranice:
        - alarms_container (UI kontejner za prikaz)
        - last_alarm_ids (skup za praćenje stanja alarma)
        - sound_enabled (logička zastavica za zvuk)
        - sound_button (UI gumb koji upravlja zvukom)
        """

        nonlocal last_alarm_ids, sound_enabled

        nonlocal last_render_time
        #----- dio gdje se podešavaju uvjeti za renderiranje
        now = datetime.now()
        alarms_df = get_aktivni_alarms()

        # Uvjeti kada treba ponovo nacrtati alarm kartice
        should_rerender = (not alarms_df.empty) and (now - last_render_time >= RENDER_INTERVAL)

        # Ako nema aktivnih alarma i ništa se nije promijenilo, preskoči update
        current_ids = set(alarms_df["id"].tolist())
        if alarms_df.empty and current_ids == last_alarm_ids:
            return

        # Ako ne treba renderati (još nije prošlo 60s), ne crtaj ponovno
        if not should_rerender and current_ids == last_alarm_ids:
            return

        
        # Only update UI if alarm list changed
        if should_rerender or current_ids != last_alarm_ids:
            last_render_time = now
            last_alarm_ids = current_ids
            alarms_container.clear()
            if alarms_df.empty:
                with alarms_container:
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
                            ).classes(
                                    'text-center text-green-900 whitespace-pre-line '
                                    'p-4 text-xl font-bold leading-loose rounded-2xl shadow-2xl')
    
                
                # Stop audio when no alarms
                ui.run_javascript("document.querySelector('audio')?.pause();")
            
            else:
                with alarms_container:
                    for _, row in alarms_df.iterrows():
                        try:
                            samo_vrijeme = datetime.strptime(row['vrijeme'], "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
                            alarm_time = datetime.strptime(row['vrijeme'], "%Y-%m-%d %H:%M:%S")
                            proteklo_minuta = int((datetime.now() - alarm_time).total_seconds() // 60)
                            proteklo_teksta = f'{proteklo_minuta} min'
                        except:
                            samo_vrijeme = row['vrijeme']
                            proteklo_teksta = 'n/a'
                        with ui.expansion().classes('border border-gray-300 rounded-xl p-2 font-semibold text-left leading-snug tracking-wide w-full') as expansion:
                            with expansion.add_slot('header'):
                                with ui.element('div').classes('grid grid-cols-[2fr_2fr_2fr_3fr] w-full gap-4 px-4'):
                                    ui.label(f'🕒 {samo_vrijeme}').classes('text-lg')
                                    ui.label(f'⏱️ {proteklo_teksta}').classes('text-lg')
                                    ui.label(f'🛏️ {row.get("soba", "N/A")}').classes('text-lg')
                                    ui.label(f'🧓 {row["korisnik"] or "NEPOZNAT"}').classes('text-lg')

                            with ui.row().classes('items-end justify-around w-full gap-4'):
                                
                                zadnji = get_zadnji_potvrdjeni_alarm_korisnika(row["korisnik"])
                                if zadnji:
                                    try:
                                        potvrda_vrijeme = datetime.strptime(zadnji['vrijemePotvrde'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y. %H:%M")
                                    except:
                                        potvrda_vrijeme = zadnji['vrijemePotvrde']
                                    
                                    ui.label(f'⏱️{potvrda_vrijeme}, 👩‍⚕️ {zadnji["osoblje"]},🚨{str(row["zone_name"]).lower()},🧓{zadnji["korisnik"]}')\
                                        .classes("text-gray-400 text-lg")                                
                                
                               
                                pin_input = ui.input(label='PIN (4 znamenke)', password=True)\
                                    .props('type=number inputmode=numeric pattern="[0-9]*"')\
                                    .classes('w-60 font-semibold text-2xl')

                                # Handler potvrde alarma    
                                def make_potvrdi_handler(alarm_id, pin_input_instance, expansion_instance):
                                    def potvrdi():
                                        pin_value = pin_input_instance.value.strip()
                                        if not validan_pin(pin_value):
                                            ui.notify('⚠️ Neispravan PIN!', type='negative')
                                            return

                                        osoblje = validiraj_osoblje(pin_value)

                                        if osoblje:
                                            potvrdi_alarm(alarm_id, osoblje[1])
                                            set_comm_flag('resetAlarm', 1)

                                            ui.notify(f'✔️ Alarm potvrđen od: {osoblje[1]}', type='positive')
                                            update_alarms()  # odmah osvježi s ispravnim stanjem iz baze
                                        else:
                                            ui.notify('❌ Neispravan PIN ili neaktivno osoblje!', type='negative')
                                    return potvrdi



                                ui.button('POTVRDI', on_click=make_potvrdi_handler(row['id'], pin_input, expansion))\
                                    .props('flat unelevated')\
                                    .classes('bg-gray-800 rounded-xl text-white hover:bg-gray-700')

                                                
                
                # Ako je zvuk isključen (npr. korisnik ga je isključio), ponovno ga uključujemo jer su se pojavili novi alarmi
                if not sound_enabled:
                    sound_enabled = True
                    ui.notify('🔔 Novi alarm – zvuk ponovno uključen', type='warning')

                # Pokreni zvuk SAMO ako postoje alarmi i audio je pauziran
                ui.run_javascript("""
                    const audio = document.querySelector('audio');
                    if (audio && audio.paused) {
                        audio.play().catch(() => {});
                    }
                """)

   
    # Initial check - play sound immediately if alarms exist
    alarms_init_check = get_aktivni_alarms()
    if not alarms_init_check.empty:
        if sound_enabled:
            ui.run_javascript("document.querySelector('audio')?.play().catch(() => {});")
    else:
        # sigurnosno zaustavi svaki mogući autoplay
        ui.run_javascript("document.querySelector('audio')?.pause();")
        
    
    # Initialize and set up periodic refresh
    update_alarms()
    ui.timer(REFRESH_INTERVAL, update_alarms)

# ------------------ Run application ------------------
ui.run(
    title="Alarm Kiosk",
    reload=True,
    dark=True
)