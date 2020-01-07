import pyaudio
import numpy as np
import time
import math
import RPi.GPIO as GPIO

#var editing
pin1 = 13
pin2 = 15 #pins for PWM
pin3 = 12
peakMult = .55 #multiplier for the volume variable "peak"

#initialization
GPIO.setmode(GPIO.BOARD)
GPIO.setup(pin1, GPIO.OUT)
GPIO.setup(pin2, GPIO.OUT)
GPIO.setup(pin3, GPIO.OUT)
RedPin = GPIO.PWM(pin1, 60)
GreenPin = GPIO.PWM(pin2, 60)
BluePin = GPIO.PWM(pin3, 60)
RedPin.start(0)
GreenPin.start(0)
BluePin.start(0)
CHUNK = 2**11
RATE = 44100
p=pyaudio.PyAudio()
stream=p.open(format=pyaudio.paInt16,channels=1,rate=RATE,input=True,
              frames_per_buffer=CHUNK)

#main code loop
for i in range(int(80000*44100/1024)): #go for a few seconds
    data = np.fromstring(stream.read(CHUNK),dtype=np.int16)
    peak = np.average(np.abs(data))*peakMult
    bars = "#"*int(200*peak/2**16)

    #sine waves which control the color fade
    RedPinMult = ((math.cos(.041 * i)) + 1) / 2
    GreenPinMult = ((math.cos(.032 * i + 650)) + 1) / 2
    BluePinMult = ((math.cos(.053 * i + 200)) + 1) / 2

    print("%04d %03d %.3f %.3f %.3f %s"%
    (i,peak/100,RedPinMult,GreenPinMult,BluePinMult,bars))

    if peak < 10000:
        RedPin.ChangeDutyCycle(peak/100 * RedPinMult)
        GreenPin.ChangeDutyCycle(peak/100 * GreenPinMult)
        BluePin.ChangeDutyCycle(peak/100 * BluePinMult)


stream.stop_stream()
stream.close()
p.terminate()
RedPin.stop()
GreenPin.stop()
BluePin.stop()
GPIO.cleanup()
