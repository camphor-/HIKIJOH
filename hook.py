import datetime
from time import sleep
from time import gmtime, strftime

from lib.lcd import lcd_string
import lib.lcd as lcd

from hue import turn_on_all_lights, turn_off_all_lights
from prometheus_exporter import set_door_metrics_open, set_door_metrics_closed

from remo_api import aircon_on, aircon_off
from curtain import open_curtain, close_curtain

def close_door_hook():
    set_door_metrics_closed()
    turn_off_all_lights()
    aircon_off()
    close_curtain()


def open_door_hook():
    set_door_metrics_open()
    turn_on_all_lights()
    aircon_on()
    open_curtain()


def show_datetime():  # 「日時」を表示
    local_time = datetime.datetime.now()
    lcd_string(strftime("%Y.%m.%d (%a)", gmtime()), lcd.LCD_LINE_1)
    lcd_string(local_time.strftime("%H:%M"), lcd.LCD_LINE_2)
    sleep(1)
