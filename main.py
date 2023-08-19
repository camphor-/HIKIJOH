# -*- coding: utf-8 -*-

import binascii
import nfc
import pigpio
from time import sleep
import time

import datetime
import pandas as pd

import lib.lcd as lcd
from lib.lcd import lcd_byte, lcd_string, lcd_init
from hook import open_door_hook, close_door_hook
from prometheus_exporter import start_prometheus_exporter


from post_alert_to_slack import check_open


SCHEDULE_LINK = "https://cal.camph.net/public/schedule.json"


class Servo:
    #set servo PIN
    servo_pin = 18
    #set switch PIN
    switch_pin = 27

    def __init__(self):
        self.pi = pigpio.pi()

        self.pi.set_mode(Servo.switch_pin, pigpio.INPUT)
        self.pi.set_pull_up_down(Servo.switch_pin, pigpio.PUD_UP)

    def switch_status(self):
        if self.pi.read(Servo.switch_pin) == 0:
            return True
        else:
            return False

    # 鍵を開ける
    def door_open(self):
        self.pi.set_servo_pulsewidth(Servo.servo_pin, 500)
        sleep(1)
        # 開放
        self.pi.set_servo_pulsewidth(Servo.servo_pin, 0)
        sleep(3)
        open_door_hook()

    # 鍵を締める
    def door_close(self):
        self.pi.set_servo_pulsewidth(Servo.servo_pin, 2500)
        sleep(1)
        # 開放
        self.pi.set_servo_pulsewidth(Servo.servo_pin, 0)
        sleep(3)
        close_door_hook()

class NFC_CARD:
    def __init__(self):
        ### NFC
        self.clf = nfc.ContactlessFrontend('usb')
        # 212F(FeliCa)
        self.target_suica = nfc.clf.RemoteTarget("212F")
        # 0003(Suica)
        self.target_suica.sensf_req = bytearray.fromhex("0000030000")
        # 212F(FeliCa) 学生証用に2つ起動させておく(suica以外のカード)
        self.target_req = nfc.clf.RemoteTarget("212F")

    def nfc_process(self):
        target = None
        target_res = self.clf.sense(self.target_suica, iterations=10, interval=0.01)
        target_res2 = self.clf.sense(self.target_req, iterations=1, interval=0.01)
        if target_res is not None:
            target = target_res
        elif target_res2 is not None:
            target = target_res2
        if target is not None:
            tag = nfc.tag.activate(self.clf,target)
            tag.sys = 3
            idm = binascii.hexlify(tag.idm)
            stridm = str(idm, 'utf-8')
            return stridm
        else:
            return None

class NFC_Data:
    def __init__(self):
        self.df = pd.read_csv('/home/pi/HIKIJOH/data/idm.csv')
    def check_registered(self,idm):
        if (self.df["idm"] == idm).sum() == 0: #登録されていなかったら
            return False
        else: #登録されていたら
            return True
    def registering_card(self,idm):
        self.df=self.df.append({'registered_date':datetime.date.today(),'idm':idm} , ignore_index=True)
        self.df.to_csv('/home/pi/HIKIJOH/data/idm.csv')


def main():
    global LCD_BACKLIGHT

    door_isopen = True
    want_close = False
    card_istouch = False

    check_open(door_isopen=door_isopen)

    card = NFC_CARD()
    servo = Servo()
    nfc_data = NFC_Data()

    start_prometheus_exporter()

    lcd_init()
    servo.door_open() ##最初は開けておく
    
    lcd_string("   Welcome to   ", lcd.LCD_LINE_1)
    lcd_string(" CAMPHOR- LOCK ", lcd.LCD_LINE_2)

    sleep(1) #LCDを1秒間点灯
    LCD_BACKLIGHT = 0x00  #バックライトオフ
    lcd_byte(0x01, lcd.LCD_CMD) #表示内容クリア

    while True:
        ret = card.nfc_process()
        if ret is not None:
            card_istouch = True
            card_touched_time = time.time()
            LCD_BACKLIGHT  = 0x08  # On
            lcd_byte(0x01, lcd.LCD_CMD) #表示内容クリア
            is_timeout = False

            if nfc_data.check_registered(ret): #idmがすでに登録されているカードだったら
                if want_close == True and door_isopen == True:
                    lcd_string(" GOOD BYE >_< ", lcd.LCD_LINE_1)
                    lcd_string(" SEE YOU AGAIN ", lcd.LCD_LINE_2)
                    servo.door_close()
                    door_isopen = False
                    want_close = False

                elif want_close == False and door_isopen == False:
                    lcd_string("   Welcome to   ", lcd.LCD_LINE_1)
                    lcd_string(" CAMPHOR- HOUSE ", lcd.LCD_LINE_2)
                    servo.door_open()
                    door_isopen = True
                    
            else: #登録されていないカードだったら
                lcd_string("  THIS CARD IS  ", lcd.LCD_LINE_1)
                lcd_string(" NOT REGISTERED ", lcd.LCD_LINE_2)
                while True: #5秒間ボタン入力を受け付ける
                    if servo.switch_status(): #ボタンの入力がされたら
                        lcd_string(" PLEASE TOUCH  ", lcd.LCD_LINE_1)
                        lcd_string(" REGISTERED CARD", lcd.LCD_LINE_2)
                        wait_master_time = time.time()

                        while True: #すでに登録されたカードのタッチを15秒待つ
                            ret_m = card.nfc_process()
                            if time.time() - wait_master_time > 15:
                                is_timeout = True
                                lcd_string("REGISTERATION IS", lcd.LCD_LINE_1)
                                lcd_string(" TIMEOUT... >_< ", lcd.LCD_LINE_2)
                                break
                            if ret_m is not None:
                                if nfc_data.check_registered(ret_m): #idmがすでに登録されているカードだったら
                                    nfc_data.registering_card(ret) #元々タッチされたカードを追加する
                                    lcd_string(" THIS CARD IS  ", lcd.LCD_LINE_1)
                                    lcd_string("REGISTERED! ^o^ ", lcd.LCD_LINE_2)
                                    sleep(1)
                                    is_timeout = True #ループから抜けるために便宜上
                                    break
                                else:
                                    lcd_string(" THIS CARD IS  ", lcd.LCD_LINE_1)
                                    lcd_string(" NOT MASTER CARD ", lcd.LCD_LINE_2)

                    if time.time() - card_touched_time > 5:
                        is_timeout = True
                    
                    if is_timeout == True:
                        is_timeout = False
                        break
        if card_istouch == True:
            if time.time() - card_touched_time > 60:
                #LCDの焼け付きを防止するために消す
                card_istouch = False
                LCD_BACKLIGHT = 0x00  #バックライトオフ
                lcd_byte(0x01, lcd.LCD_CMD) #表示内容クリア

        if servo.switch_status():
            if want_close != True:
                LCD_BACKLIGHT  = 0x08  # On
                lcd_byte(0x01, lcd.LCD_CMD) #表示内容クリア
                lcd_string("HOUSE CLOSE MODE", lcd.LCD_LINE_1)
                lcd_string(" TOUCH KEY ^o^ ", lcd.LCD_LINE_2)
                want_close_time = time.time()
                want_close = True

        if want_close == True:
            if time.time() - want_close_time > 60:
                #LCDの焼け付きを防止するために消す
                want_close = False
                LCD_BACKLIGHT = 0x00  #バックライトオフ
                lcd_byte(0x01, lcd.LCD_CMD) #表示内容クリア

        # 開館の20分前から3時間後までの間にドアが開いていない場合はSlackに通知
        check_open(door_isopen=door_isopen)


if __name__ == '__main__':
    main()
