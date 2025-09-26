import os
import sqlite3
import streamlit as st
from typing import Optional, List
from admin import BASE_DIR, DB_PATH

# =================== KONFIG ===================

STATIC_DIR = os.path.join(BASE_DIR, "static")
COMM_KEY = "sound_file"

# =================== DB HELPERI ===================
def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def get_comm_value(key: str) -> Optional[str]:
    try:
        with _conn() as conn:
            cur = conn.execute("SELECT value FROM comm WHERE key = ? LIMIT 1;", (key,))
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        st.error(f"Greška pri čitanju iz comm: {e}")
        return None

def set_comm_value(key: str, value: str) -> bool:
    try:
        with _conn() as conn:
            # Kreiraj zapis ako ne postoji
            conn.execute(
                "INSERT INTO comm(key, value) SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM comm WHERE key = ?);",
                (key, value, key),
            )
            # Ažuriraj vrijednost
            conn.execute("UPDATE comm SET value = ? WHERE key = ?;", (value, key))
        return True
    except Exception as e:
        st.error(f"Greška pri spremanju u comm: {e}")
        return False

def ensure_comm_key(key: str) -> None:
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO comm(key, value) SELECT ?, '' WHERE NOT EXISTS (SELECT 1 FROM comm WHERE key = ?);",
                (key, key),
            )
    except Exception as e:
        st.error(f"Greška pri inicijalizaciji comm zapisa: {e}")

# =================== FILE HELPERI ===================
ALLOWED_EXT = {".mp3", ".wav"}

def list_sound_files() -> List[str]:
    if not os.path.isdir(STATIC_DIR):
        return []
    files = []
    for name in os.listdir(STATIC_DIR):
        path = os.path.join(STATIC_DIR, name)
        ext = os.path.splitext(name)[1].lower()
        if os.path.isfile(path) and ext in ALLOWED_EXT:
            files.append(name)
    # Sortiraj po imenu (case-insensitive)
    files.sort(key=lambda x: x.lower())
    return files

def make_sound_path(s_file: str) -> str:
    # Efektivni path koji koristi aplikacija
    return os.path.join(BASE_DIR, "static", s_file)

# =================== UI ===================
st.set_page_config(page_title="Odaberi ton alarma", page_icon="🔊", layout="centered")
st.title("🔊 Odabir alarma (kiosk)")

# Osiguraj da postoji zapis u comm za sound_file
ensure_comm_key(COMM_KEY)

# Učitaj dostupne tonove
available = list_sound_files()

if not available:
    st.warning(f"Nema pronađenih .mp3/.wav datoteka u: `{STATIC_DIR}`.")
    st.stop()

# Trenutno spremljen naziv (ako postoji)
current_sfile = get_comm_value(COMM_KEY) or ""

# Ako trenutni zapis nije među dostupnima, predloži prvi
if current_sfile not in available:
    suggested = available[0]
else:
    suggested = current_sfile

st.caption(f"Direktorij s tonovima: `{STATIC_DIR}`")

# Odabir tona
selected = st.selectbox(
    "Odaberite ton",
    options=available,
    index=available.index(suggested) if suggested in available else 0,
    help="Datoteka mora biti .mp3 ili .wav u mapi static.",
)

# Preslušavanje
sound_path = make_sound_path(selected)
try:
    st.audio(sound_path)  # Streamlit prepoznaje lokalnu datoteku
except Exception as e:
    st.error(f"Ne mogu reproducirati ton: {e}")

# Spremanje u bazu
col1, col2 = st.columns([1, 1])
with col1:
    if st.button("💾 Spremi odabrani ton u bazu"):
        ok = set_comm_value(COMM_KEY, selected)
        if ok:
            st.success(f"Spremljeno: key='{COMM_KEY}', value='{selected}'")
with col2:
    # Prikaži trenutno spremljeni naziv iz baze
    refreshed = get_comm_value(COMM_KEY) or ""
    st.metric("Trenutno u bazi (value)", refreshed if refreshed else "—")

st.divider()

# Informativno prikaži kako se formira SOUND_FILE u ostatku projekta
effective_sfile = get_comm_value(COMM_KEY) or selected
effective_path = make_sound_path(effective_sfile)
st.write("**Efektivni path koji koristi aplikacija (SOUND_FILE):**")
st.code(
    f"SOUND_FILE = os.path.join(BASE_DIR, 'static', '{effective_sfile}')\n# => {effective_path}",
    language="python",
)

# Dodatno: kratak popis svih pronađenih tonova
with st.expander("📄 Popis pronađenih tonova"):
    for f in available:
        st.write(f"- {f}")
