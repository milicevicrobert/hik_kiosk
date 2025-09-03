# Kiosk HIK - Alarmni sustav za Dom Buzin

Sustav za nadzor korisnika s dva sučelja: **NiceGUI kiosk** za tableta i **Streamlit admin** za upravljanje.

## 📁 Struktura projekta

```
kiosk_hik/
├── app/
│   ├── admin_app.py              # Streamlit glavna aplikacija (admin sučelje)
│   ├── axpro/                    # HIKVision AX PRO integracija
│   │   ├── alarm_scaner.py       # Čitanje alarma iz HIKVision
│   │   ├── alarm_scaner_sim.py   # Simulacija za testiranje
│   │   ├── axpro_auth.py         # Autentifikacija s AX PRO
│   │   ├── ax_config.py          # Konfiguracija AX PRO
│   │   ├── db.py                 # Database operacije
│   │   ├── init_db.py            # Inicijalizacija baze podataka
│   │   └── ucitaj_zone.py        # Učitavanje zona iz sustava
│   ├── data/
│   │   └── alarmni_sustav.db     # SQLite baza podataka
│   ├── niceGui/
│   │   ├── main_kiosk.py         # 🔔 KIOSK - Tablet sučelje za potvrdu alarma
│   │   ├── nice_config.py        # Konfiguracija NiceGUI
│   │   └── test_alarm.mp3        # Zvuk alarma
│   ├── pages/                    # Streamlit stranice (admin)
│   │   ├── 2_Testiranje.py       # Test funkcionalnosti
│   │   ├── 3_Kiosk.py            # Kiosk preview
│   │   ├── 4_Pregled.py          # Pregled aktivnih alarma
│   │   ├── 5_osoblje.py          # Upravljanje osobljem
│   │   ├── 6_korisnici.py        # Upravljanje korisnicima
│   │   ├── 7_zone.py             # Upravljanje zonama
│   │   └── 7_Alarmi.py           # 📊 NOVI - Pregled i filtracija alarma
│   └── static/                   # Statični resursi
│       ├── alarm_base64.py       # Base64 kodiranje zvukova
│       ├── *.mp3, *.b64          # Audio datoteke
│       └── logo.png, logo.svg    # Logotipovi
├── requirements.txt              # Python dependencies
└── stert_kiosk_niceGui.bat      # Windows batch za pokretanje
```

## 🚀 Kako pokrenuti

### 1. Kiosk (tablet sučelje)
```bash
cd app/niceGui
python main_kiosk.py
```
**Ili koristite:** `stert_kiosk_niceGui.bat`

### 2. Admin sučelje (Streamlit)
```bash
cd app
streamlit run admin_app.py
```

## 🔧 Glavne komponente

### 📱 **KIOSK** (`niceGui/main_kiosk.py`)
- **Svrha**: Tablet sučelje za osoblje - potvrda alarma PIN kodom
- **Funkcije**:
  - Prikaz aktivnih alarma u real-time
  - Zvučna signalizacija
  - Responsive design za tablete/mobitele (landscape)
  - Automatsko osvježavanje
- **Optimiziran za**: Samsung tableti, landscape orijentacija

### 🖥️ **ADMIN** (`admin_app.py` + `pages/`)
- **Svrha**: Web admin za upravljanje sustavom
- **Stranice**:
  - **4_Pregled.py**: Aktivni alarmi
  - **7_Alarmi.py**: 📊 **NOVA** - Filtracija i pregled svih alarma
  - **5_osoblje.py**: Upravljanje osobljem (PIN kodovi)
  - **6_korisnici.py**: Upravljanje korisnicima
  - **7_zone.py**: Konfiguracija zona

### 🔌 **INTEGRACIJA** (`axpro/`)
- **alarm_scaner.py**: Čita alarme iz HIKVision AX PRO sustava
- **axpro_auth.py**: Autentifikacija s HIKVision API
- **db.py**: SQLite operacije (alarmi, korisnici, osoblje, zone)

## 📊 Baza podataka (`data/alarmni_sustav.db`)

**Tablice:**
- `alarms` - Svi alarmi (aktivni/potvrđeni)
- `korisnici` - Korisnici sustava
- `osoblje` - Osoblje s PIN kodovima
- `zone` - Zone/sobe
- `comm` - Komunikacijske zastavice

## 🎯 Ključne značajke

### ✅ **Dodano u zadnjim izmjenama:**
- 📊 **7_Alarmi.py** - Nova stranica za filtraciju alarma po:
  - Korisniku, osoblju, datumu
  - Prikaz broja rezultata
  - Sigurno brisanje starih alarma
- 📱 **Mobilna optimizacija** - Tailwind responsive klase
- 🔄 **Performanse** - Lokalni timer umjesto punog osvježavanja

### 🛠️ **Konfiguracijski fileovi:**
- `nice_config.py` - NiceGUI postavke (DB path, sound path)
- `ax_config.py` - HIKVision AX PRO konfiguracija

## 🔧 Deployment

1. **Windows server/PC**: Koristite `.bat` datoteku
2. **Tablet kiosk**: Otvorite browser na `http://server:8080`
3. **Admin pristup**: Otvorite `http://server:8501`

## 📝 Napomene

- **Kiosk** je optimiziran za **landscape** prikaz na tabletima
- **Samsung browser** kompatibilnost uključena
- **Real-time** ažuriranje bez potrebe za ručnim osvježavanjem
- **Responsive** design pokriva desktop, tablet i mobitel