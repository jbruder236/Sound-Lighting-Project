import pyaudio
import numpy as np
import time
import math
import RPi.GPIO as GPIO

#var editing
pin1 = 12
pin2 = 13 #pins for PWM
pin3 = 15
peakMult = 1 #multiplier for the volume variable "peak"

#initialization
GPIO.setmode(GPIO.BOARD)
GPIO.setup(pin1, GPIO.OUT)
GPIO.setup(pin2, GPIO.OUT)
GPIO.setup(pin3, GPIO.OUT)
Rpin = GPIO.PWM(pin1, 50)
Rpin2 = GPIO.PWM(pin2, 50)
Rpin3 = GPIO.PWM(pin3, 50)
Rpin.start(0)
Rpin2.start(0)
Rpin3.start(0)
CHUNK = 2**11
RATE = 44100
p=pyaudio.PyAudio()
stream=p.open(format=pyaudio.paInt16,channels=1,rate=RATE,input=True,
              frames_per_buffer=CHUNK)

#main code loop
for i in range(int(80000*44100/1024)): #go for a few seconds
    data = np.fromstring(stream.read(CHUNK),dtype=np.int16)
    peak = np.average(np.abs(data))*peakMult
    bars = "#"*int(50*peak/2**16)

    #sine waves which control the color fade
    pin1mult = ((math.cos(.041 * i)) + 1) / 2
    pin2mult = ((math.cos(.032 * i + 650)) + 1) / 2
    pin3mult = ((math.cos(.053 * i + 200)) + 1) / 2

    print("%04d %05d %.3f %.3f %.3f %s"%
    (i,peak,pin1mult,pin2mult,pin3mult,bars))

    if peak < 10000:
        Rpin.ChangeDutyCycle(peak/100 * pin1mult)
        Rpin2.ChangeDutyCycle(peak/100 * pin2mult)
        Rpin3.ChangeDutyCycle(peak/100 * pin3mult)


stream.stop_stream()
stream.close()
p.terminate()
Rpin.stop()
GPIO.cleanup()
