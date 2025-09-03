import os

SOUND_FILE = os.path.join(os.path.dirname(__file__), 'test_alarm.mp3')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(BASE_DIR, 'data', 'alarmni_sustav.db')