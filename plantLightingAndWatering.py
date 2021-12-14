# -*- coding: utf-8 -*-
import paho.mqtt.client as mqtt
import random
import json  
import datetime 
import time
import seeed_si114x         #用來讀取陽光感測器讀數
import signal
import RPi.GPIO as GPIO
import threading


#設定樹莓派接線以及各變數初始值
GPIO.setup(17, GPIO.OUT, initial=GPIO.LOW)    #樹莓派接線 gpio 17 relay for pump
GPIO.setup(18, GPIO.OUT, initial=GPIO.HIGH)   #gpio 18 relay for light
SI1145 = seeed_si114x.grove_si114x()
manualLightEnable="off"
manualLight="off"
autoLight="off"
timeLightEnable="off"
lightStartTime=datetime
lightEndTime=datetime
timeWaterEnable="off"
waterTime1=datetime

# 設置日期時間的格式
ISOTIMEFORMAT = '%m/%d %H:%M:%S'

# 連線設定
# 初始化本地端程式
client = mqtt.Client()

# 設定連線資訊(IP, Port, 連線時間)
client.connect("test.mosquitto.org", 1883, 60)

#連線後訂閱client端會發佈的主題
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("manualLight")
    client.subscribe("autoLight")
    client.subscribe("timeLightEnable")
    client.subscribe("lightStartTime")
    client.subscribe("lightEndTime")
    client.subscribe("clientRefresh")
    client.subscribe("manualLightEnable")
    client.subscribe("clientWatering")
    client.subscribe("timeWaterEnable")
    client.subscribe("waterTime1")
    print("ok")

# 設定連線的動作
client.on_connect = on_connect

#發佈目前的狀態給用戶
def refresh_pub():
    if GPIO.input(18) == GPIO.HIGH:
        client.publish("currentLightState", "off")
        print("pub currentLightState off")
    if GPIO.input(18)== GPIO.LOW:
        client.publish("currentLightState", "on")
        print("pub currentLightState on")
    client.publish("currentVisibleLight", str(SI1145.ReadVisible))
    print("pub currentVisibleLight %s"%(str(SI1145.ReadVisible)))


#開啟澆水裝置
def watering():
    GPIO.output(17,GPIO.HIGH)
    time.sleep(12)    #可調整澆水時間
    GPIO.output(17,GPIO.LOW)
    
    
#確認是否開啟定時澆水
def timeWaterCheck():
    global timeWaterEnable
    global waterTime1
    print("timeWaterCheck")
    if timeWaterEnable=="on":
        print("timeWaterEnable:on")
        print("waterTime1=%s"%(waterTime1))
        try:
            now=datetime.datetime.now()
            if now.minute==waterTime1.minute and now.second<15:
                watering()
        except Exception as e:
            print("%s"%(e))
        
    elif timeWaterEnable == "off":
        print("timeWaterEnable: off")

    
#確認是否開啟自動判斷開燈
def autoCheck():
    global autoLight
    
    print("auto check")
    threshold=262     #auto的閥值
    if autoLight == "on":
        print("autoLight: on")
        GPIO.output(18,GPIO.HIGH)
        if SI1145.ReadVisible>=threshold:
            GPIO.output(18,GPIO.HIGH)
        elif SI1145.ReadVisible<threshold:
            GPIO.output(18,GPIO.LOW)
    elif autoLight=="off":
        print("autoLight: off")
        GPIO.output(18,GPIO.HIGH)
    
    
#確認是否開啟定時開關燈
def timeCheck():
    global timeLightEnable
    global lightStartTime
    global lightEndTime

    print("time check")
    if timeLightEnable == "on":
        print("timeLightEnable: on")
        try:
            now=datetime.datetime.now()
            if lightEndTime.time() < lightStartTime.time():
                print("m1")   #設定的時間段有經過半夜十二點
                if now.time()>=lightStartTime.time() and now.time()<=datetime.time.max:
                    print("已到設定的時間-開燈")
                    GPIO.output(18,GPIO.LOW)
                elif now.time()>=datetime.time.min and now.time()<=lightEndTime.time():
                    print("已到設定的時間-開燈")
                    GPIO.output(18,GPIO.LOW)
                else:
                    print("不在設定的時間範圍內-關燈")
                    GPIO.output(18,GPIO.HIGH)
                    autoCheck()
            elif lightEndTime.time() > lightStartTime.time():
                print("m2")   #設定的時間段沒經過半夜12點
                if now.time()>=lightStartTime.time() and now.time()<=lightEndTime.time():
                    print("已到設定的時間-開燈")
                    GPIO.output(18,GPIO.LOW)
                else:
                    print("不在設定的時間範圍內-關燈")
                    GPIO.output(18,GPIO.HIGH)
                    autoCheck()
        except Exception as e:
            print("%s"%(e))
        
    elif timeLightEnable == "off":
        print("timeLightEnable: off")
        autoCheck()
    
#確認是否手動控制燈的開關
def forceCheck():    
    global manualLightEnable
    global manualLight
    
    print("force check")
    if manualLightEnable == "on":
        if manualLight=="on":
            GPIO.output(18,GPIO.LOW)
        elif manualLight=="off":
            GPIO.output(18,GPIO.HIGH)
    elif manualLightEnable == "off":  
        timeCheck()
    
    
#光照燈基本流程 
#判斷是否手動控制開關forceCheck()->是否定時開關timeCheck()->
#->是否在變暗時自動開關autoCheck()-> 結束後更新資訊refresh_pub()
#澆水定時檢查時間到了沒timeWaterCheck()
#更新資訊refresh_pub()
def main():
    print("main check")
    forceCheck()
    timeWaterCheck()
    refresh_pub()
    #GPIO.cleanup()


#開始線程每隔幾秒重複執行一次main()，以進行定時設定的確認和資訊的更新
class TimerClass(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.event = threading.Event()

    def run(self):
        while not self.event.is_set():
            main()
            self.event.wait( 5 )  #每隔幾秒執行一次

    def stop(self):
        self.event.set()

tmr = TimerClass()
tmr.start()


#收到訊息時的動作，儲存使用者發送的設定
def on_message(client, userdata, msg):
    msg.payload = msg.payload.decode("utf-8") #一定要先decode才能正常操作，否則會出錯                    https://stackoverflow.com/questions/40922542/python-why-is-my-paho-mqtt-message-different-than-when-i-sent-it
    #debug
    print(msg.topic+" "+ msg.payload)
    global manualLightEnable
    global manualLight
    global example
    global autoLight
    global timeLightEnable
    global lightStartTime
    global lightEndTime
    global timeWaterEnable
    global waterTime1
    
    if msg.topic == "clientRefresh":
        refresh_pub()
        
    if msg.topic == "clientWatering":
        watering()
        
    if msg.topic == "timeWaterEnable":
        if str(msg.payload)=="on":
            timeWaterEnable="on"
        if str(msg.payload)=="off":
            timeWaterEnable="off"
            
    if msg.topic == "waterTime1":
        try:
            waterTime1=datetime.datetime.strptime(str(msg.payload),"%H-%M")
            print("waterTime1= %s"%(waterTime1))
        except Exception as e:
            print("%s"%(e))
        
    if msg.topic == "manualLightEnable":
        if str(msg.payload) == "on":
            manualLightEnable = "on"
            autoLight="off"
            print("manualLightEnable %s"%(manualLightEnable))
        if str(msg.payload) == "off":
            manualLightEnable = "off"
            print("manualLightEnable %s"%(manualLightEnable))
            
    if msg.topic == "manualLight":
        if str(msg.payload) == "on":
            manualLight="on"
        if str(msg.payload) == "off":
            manualLight="off"
            
    if manualLightEnable == "off":        
        if msg.topic == "autoLight":
            if str(msg.payload) == "on":
                autoLight="on"
            if str(msg.payload) == "off":
                autoLight="off"
                
        if msg.topic == "timeLightEnable":
            if str(msg.payload) == "on":
                timeLightEnable="on"
            if str(msg.payload) == "off":
                timeLightEnable="off"
        if msg.topic == "lightStartTime":
            try:
                lightStartTime=datetime.datetime.strptime(str(msg.payload),"%H-%M")
                print("start= %s"%(lightStartTime))
            except Exception as e:
                print("%s"%(e))
        if msg.topic == "lightEndTime":
            try:
                lightEndTime=datetime.datetime.strptime(str(msg.payload),"%H-%M")
                print("end= %s"%(lightEndTime))
            except Exception as e:
                print("%s"%(e))

    main()
    refresh_pub()


# 設定接收訊息的動作
client.on_message = on_message
    
# 開始連線，執行設定的動作和處理重新連線問題
client.loop_forever()


if __name__  == '__main__':
    main()
