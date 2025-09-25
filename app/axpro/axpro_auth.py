import hashlib
import time
import requests
import xml.etree.ElementTree as ET

# AX PRO postavke
HOST = "192.168.1.159"
USERNAME = "admin"
PASSWORD = "D0m1nat0r."


# Funkcija za SHA-256 hashiranje
def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Dohvati parametre sesije (sessionID, challenge, salt itd.)
def get_session_params(host=HOST, username=USERNAME):
    url = f"http://{host}/ISAPI/Security/sessionLogin/capabilities?username={username}"
    r = requests.get(url)
    r.raise_for_status()
    ns = {"ns": "http://www.hikvision.com/ver20/XMLSchema"}
    root = ET.fromstring(r.text)
    return {
        "sessionID": root.findtext(".//ns:sessionID", namespaces=ns),
        "challenge": root.findtext(".//ns:challenge", namespaces=ns),
        "salt": root.findtext(".//ns:salt", namespaces=ns),
        "salt2": root.findtext(".//ns:salt2", namespaces=ns),
        "isIrreversible": root.findtext(".//ns:isIrreversible", namespaces=ns)
        == "true",
        "iterations": int(root.findtext(".//ns:iterations", namespaces=ns)),
    }


# Kodiraj lozinku za prijavu
def encode_password(cap, username=USERNAME, password=PASSWORD):
    if cap["isIrreversible"]:
        result = sha256(f"{username}{cap['salt']}{password}")
        result = sha256(f"{username}{cap['salt2']}{result}")
        result = sha256(f"{result}{cap['challenge']}")
        for _ in range(2, cap["iterations"]):
            result = sha256(result)
    else:
        result = sha256(password) + cap["challenge"]
        for _ in range(1, cap["iterations"]):
            result = sha256(result)
    return result


# ---------- OVO DOLJE SU FUNKCIJE KOJE SE POZIVAJU IZNAD MOŽEŠ ZANEMARITI TO JE SPAJANJE I AUTORIZACIJA ---------


# Login na AX PRO centralu – vraća session cookie
def login_axpro(host=HOST, username=USERNAME, password=PASSWORD):
    cap = get_session_params(host, username)
    encoded_pw = encode_password(cap, username, password)

    session_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <SessionLogin>
            <userName>{username}</userName>
            <password>{encoded_pw}</password>
            <sessionID>{cap['sessionID']}</sessionID>
        </SessionLogin>"""

    timestamp = int(time.time())
    url = f"http://{host}/ISAPI/Security/sessionLogin?timeStamp={timestamp}"
    headers = {
        "Content-Type": "application/xml",
        "User-Agent": "python-requests",
        "Accept": "*/*",
        "Connection": "Keep-Alive",
    }

    r = requests.post(url, headers=headers, data=session_xml)
    r.raise_for_status()
    cookie = r.headers.get("Set-Cookie", "").split(";")[0]
    return cookie


# Dohvaća sve zone iz centrale i vraća json
def get_zone_status(cookie, host=HOST):
    url = f"http://{host}/ISAPI/SecurityCP/status/zones?format=json"
    headers = {"Cookie": cookie}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()


# Briše sve alarme uz centrale, resetira alarme svih zona.
def clear_axpro_alarms(cookie, subsystem_no=1, host=HOST):
    """Briše sve alarme na AX PRO centrali za zadani subsystem (1-4)"""
    url = (
        f"http://{host}/ISAPI/SecurityCP/control/clearAlarm/{subsystem_no}?format=json"
    )
    headers = {"Cookie": cookie, "Content-Type": "application/json"}
    response = requests.put(url, headers=headers)
    response.raise_for_status()
    return response.status_code, response.text
