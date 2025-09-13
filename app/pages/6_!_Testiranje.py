import streamlit as st
import pandas as pd
from axpro.axpro_auth import login_axpro, get_zone_status, clear_axpro_alarms, HOST,USERNAME,PASSWORD

st.set_page_config(page_title="AX PRO Test", layout="wide")


st.title("🧪 Testiranje komunikacije s AX PRO centralom")

# Prikaz zona
if st.button("🔌 Spoji se i prikaži zone"):
    try:
        cookie = login_axpro()
        zones_data = get_zone_status(cookie)
        zone_list = [z["Zone"] for z in zones_data.get("ZoneList", [])]

        st.success(f"Učitano {len(zone_list)} zona.")
        df = pd.DataFrame(zone_list)
        st.dataframe(df)

        active = df[df["alarm"] == True]
        if not active.empty:
            st.warning(f"‼️ Aktivni alarmi ({len(active)}):")
            for _, z in active.iterrows():
                st.markdown(f"- **{z['name']}** (ID: {z['id']})")
        else:
            st.info("Nema aktivnih alarma.")
    except Exception as e:
        st.error(f"Greška: {e}")

# Reset alarma
st.markdown("---")
st.subheader("🧹 Resetiraj sve alarme na centrali")

if st.button("🧯 Resetiraj alarme"):
    try:
        cookie = login_axpro()
        status, response_text = clear_axpro_alarms(cookie)
        st.success(f"Alarmi resetirani (status: {status})")
        st.code(response_text)
    except Exception as e:
        st.error(f"Greška pri resetiranju: {e}")

st.markdown('<hr style="margin-top:2em; margin-bottom:0.5em;">', unsafe_allow_html=True)
st.markdown('<div style="text-align:right; color:gray; font-size:0.95em;">&copy; RM 2025</div>', unsafe_allow_html=True)
