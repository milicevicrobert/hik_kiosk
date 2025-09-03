from nicegui import ui
import os


from app.pages.home_page import home_page
from app.pages.kiosk_page import kiosk_page
from app.pages.admin_page import admin_page



ui.run(
    title="Alarm Kiosk",
    reload=False,
    dark=True
)