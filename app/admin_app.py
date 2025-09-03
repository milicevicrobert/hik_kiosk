import streamlit as st
import os
from admin_config import DB_PATH

st.set_page_config(
    page_title="Alarmni Sustav za praćenje korisnika",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown("""
    <style>
        div[data-testid="stToolbar"] button {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🔧 Administratorski modul za konfiguraciju sustava alarma")

# CSS za dark/light mod kompatibilno upozorenje
st.markdown("""
<style>
.warning-box {
    padding: 16px;
    border-left: 5px solid #e60000;
    border-radius: 4px;
    margin-top: 1em;
    font-size: 0.95rem;
}

@media (prefers-color-scheme: dark) {
    .warning-box {
        background-color: #330000;
        color: #ffcccc;
    }
}

@media (prefers-color-scheme: light) {
    .warning-box {
        background-color: #ffe5e5;
        color: #660000;
    }
}
</style>

<div class="warning-box">
<strong>⚠️ UPOZORENJE:</strong><br><br>
Ovaj modul je <strong>isključivo za administratore</strong> aplikacije.<br><br>
• Neovlaštena ili nestručna uporaba može uzrokovati <strong>nepovratne greške</strong> u bazi podataka.<br>
• Promjene treba vršiti samo uz stručni nadzor.<br>
• Ne preporučuje se korištenje bez prethodnog sigurnosnog backup-a.
</div>
""", unsafe_allow_html=True)



st.markdown("""
Ovaj administracijski modul razvijen je isključivo za potrebe ustanove **Dom Buzin** 
u svrhu tehničke konfiguracije sustava za nadzor korisnika.

Sadržaj i funkcionalnosti dostupni su isključivo ovlaštenom osoblju s administrativnim pristupom.

<br>
<sub>© Robert M., 2025 – Sva prava pridržana.</sub>
""", unsafe_allow_html=True)

if not os.path.exists(DB_PATH):
    st.error("⚠️ Baza podataka ne postoji. Provjerite putanju.")
    st.stop()
