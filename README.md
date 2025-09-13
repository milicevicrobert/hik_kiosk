# Kiosk HIK - Alarmni sustav za Dom Buzin

Sustav za nadzor korisnika s dva sučelja: **NiceGUI kiosk** za tableta i **Streamlit admin** za upravljanje.

## 📁 Struktura projekta

```
kiosk_hik/
├── app/
│   ├── admin_app.py              # Streamlit glavna aplikacija (admin sučelje)
│   ├── axpro/                    # HIKVision AX PRO integracija
│   │   ├── alarm_scaner.py       # 🏭 PRODUCTION - Čita alarme iz AX PRO
│   │   ├── alarm_scaner_sim.py   # 🧪 SIMULATOR - Generira test alarme
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
└── README.md                     # Ova dokumentacija
```

## 🚀 Kako pokrenuti

### 🖥️ **Admin Control Center** (PREPORUČENO)
```bash
cd app
streamlit run admin_app.py   # Admin na http://localhost:8501
```
**Zatim:**
- Idite na stranicu **"B_Service_Management"**
- Odaberite **"🏭 Production Mode"** (s AX PRO centralom)
- Ili **"🧪 Development Mode"** (simulacija bez centrale)
- Sve se pokreće automatski jednim klikom!

### 🔧 **Ručno pokretanje** (opcionalno)
```bash
# Production (s HIKVision centralom)
cd app/axpro && python alarm_scaner.py        # AX PRO Scanner
cd app/niceGui && python main_kiosk.py        # Kiosk (http://localhost:8080)

# Development (simulacija)  
cd app/axpro && python alarm_scaner_sim.py    # Simulator
cd app/niceGui && python main_kiosk.py        # Kiosk (http://localhost:8080)
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
- **Svrha**: Web admin za upravljanje cijeli sustavom
- **Stranice**:
  - **A_System_Status.py**: 📊 Real-time monitoring servisa
  - **B_Service_Management.py**: 🚀 Pokretanje/zaustavljanje servisa  
  - **4_Pregled.py**: Aktivni alarmi
  - **7_Alarmi.py**: 📊 Filtracija i pregled svih alarma
  - **5_osoblje.py**: Upravljanje osobljem (PIN kodovi)
  - **6_korisnici.py**: Upravljanje korisnicima
  - **7_zone.py**: Konfiguracija zona
  - **9_Database.py**: Database management

### 🔌 **INTEGRACIJA** (`axpro/`)
- **alarm_scaner.py**: 🏭 **PRODUCTION** - Čita alarme iz HIKVision AX PRO sustava
- **alarm_scaner_sim.py**: 🧪 **DEVELOPMENT** - Simulira alarme kad nema AX PRO centrale
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
- � **Service Management** - Pokretanje svih servisa iz admin sučelja
- 📊 **Real-time System Status** - A_System_Status.py za monitoring
- 💓 **Heartbeat Monitoring** - Automatska provjera rada servisa
- 📊 **7_Alarmi.py** - Filtracija alarma po korisniku, osoblju, datumu
- 📱 **Mobilna optimizacija** - Tailwind responsive klase
- 🔄 **Performanse** - Lokalni timer umjesto punog osvježavanja
- 🗃️ **Database Management** - Kreiranje i održavanje baze preko admin sučelja

### 🛠️ **Konfiguracijski fileovi:**
- `nice_config.py` - NiceGUI postavke (DB path, sound path)
- `ax_config.py` - HIKVision AX PRO konfiguracija

## 🔧 Deployment

### 🖥️ **Jednostavno pokretanje**
1. **Otvorite Admin Control Center**: `streamlit run admin_app.py`
2. **Service Management stranica** → Odaberite mode:
   - **🏭 Production**: HIKVision AX PRO + Kiosk
   - **🧪 Development**: Simulator + Kiosk  
3. **Kiosk dostupan na**: `http://localhost:8080`
4. **Real-time monitoring**: A_System_Status stranica

### 🏭 **Production Environment**  
- **Windows server s HIKVision AX PRO mrežnim pristupom**
- **Admin Control Center** → Production Mode
- **Automatski heartbeat monitoring**

### 🧪 **Development Environment**
- **Lokalni PC bez HIKVision centrale**  
- **Admin Control Center** → Development Mode
- **Simulator** automatski generira test alarme

## 📝 Napomene

### 🏭 **Production (s HIKVision AX PRO)**
- **alarm_scaner.py** čita prave alarme iz centrale
- **Real-time** komunikacija s HIKVision API
- **Network dependency** - trebate pristup AX PRO centrali

### 🧪 **Development (simulator)**
- **alarm_scaner_sim.py** generira test alarme
- **Offline rad** - ne treba HIKVision centrala
- **Kontrolirano testiranje** - možete simulirati različite scenarije

### 📱 **Admin optimizacije**
- **Service Management** - Pokretanje servisa jednim klikom
- **Real-time monitoring** - Live status svih komponenti  
- **Heartbeat tracking** - Automatska provjera rada servisa
- **Quick Start modes** - Production vs Development mode
- **Database management** - Kreiranje i održavanje baze

### 📱 **Kiosk optimizacije**
- **Landscape** prikaz optimiziran za tablete
- **Samsung browser** kompatibilnost uključena
- **Real-time** ažuriranje bez potrebe za ručnim osvježavanjem
- **Responsive** design pokriva desktop, tablet i mobitel


dodatak:

NSSM SERVIS INSTALACIJA - DOM BUZIN KIOSK SISTEM
=================================================

PRIPREMA:
---------
1. Download NSSM sa https://nssm.cc/download
2. Raspakiraj nssm.exe u C:\Tools\nssm\
3. Dodaj C:\Tools\nssm u PATH varijablu
4. Restartaj Command Prompt
5. Testiraj: nssm

INSTALACIJA SERVISA:
--------------------
Otvori Command Prompt kao Administrator i idi u projekt folder:
cd c:\Users\milic\dev\py\kiosk_hik

1. KIOSK SERVIS (NiceGUI aplikacija):
   nssm install KioskService "%cd%\kiosk.bat"
   nssm set KioskService DisplayName "Dom Buzin - Kiosk"
   nssm set KioskService Description "Alarm Kiosk aplikacija za tablet"
   nssm set KioskService Start SERVICE_AUTO_START
   nssm set KioskService AppDirectory "%cd%"
   nssm set KioskService AppExit Default Restart
   nssm set KioskService AppRestartDelay 10000

2. ADMIN SERVIS (Streamlit aplikacija):
   nssm install AdminService "%cd%\admin.bat"
   nssm set AdminService DisplayName "Dom Buzin - Admin"
   nssm set AdminService Description "Admin panel za upravljanje alarmima"
   nssm set AdminService Start SERVICE_AUTO_START
   nssm set AdminService AppDirectory "%cd%"
   nssm set AdminService AppExit Default Restart
   nssm set AdminService AppRestartDelay 10000

3. AXPRO SERVIS (Alarm scanner):
   nssm install AxproService "%cd%\axpro.bat"
   nssm set AxproService DisplayName "Dom Buzin - AxPro Scanner"
   nssm set AxproService Description "AxPro alarm scanner servis"
   nssm set AxproService Start SERVICE_AUTO_START
   nssm set AxproService AppDirectory "%cd%"
   nssm set AxproService AppExit Default Restart
   nssm set AxproService AppRestartDelay 10000

POKRETANJE SERVISA:
-------------------
net start KioskService
net start AdminService
net start AxproService

ZAUSTAVLJANJE SERVISA:
----------------------
net stop KioskService
net stop AdminService
net stop AxproService

PROVJERA STATUSA:
-----------------
sc query KioskService
sc query AdminService
sc query AxproService

UKLANJANJE SERVISA:
-------------------
net stop KioskService && nssm remove KioskService confirm
net stop AdminService && nssm remove AdminService confirm
net stop AxproService && nssm remove AxproService confirm

KORISNI PORTOVI:
----------------
- Kiosk aplikacija: http://localhost:8080
- Admin panel: http://localhost:8501
- AxPro scanner: background servis (nema web interface)

NAPOMENE:
---------
- Svi servisi se automatski pokreću pri boot-u računala
- U slučaju crash-a, servisi se restartaju nakon 10 sekundi
- Logovi se mogu vidjeti u Windows Event Viewer
- Za promjene u kodu, restartaj odgovarajući servis