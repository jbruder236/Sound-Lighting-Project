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
CosMult = .65

#initialization
GPIO.setmode(GPIO.BOARD)
GPIO.setup(pin1, GPIO.OUT)
GPIO.setup(pin2, GPIO.OUT)
GPIO.setup(pin3, GPIO.OUT)
GreenPin = GPIO.PWM(pin1, 60)
BluePin = GPIO.PWM(pin2, 60)
RedPin = GPIO.PWM(pin3, 60)
RedPin.start(0)
GreenPin.start(0)
BluePin.start(0)
CHUNK = 2**11
RATE = 44100
p=pyaudio.PyAudio()
stream=p.open(format=pyaudio.paInt16,channels=1,rate=RATE,input=True,
              frames_per_buffer=CHUNK)
lastpeak = 0
peak = 0
#main code loop
for i in range(int(80000*44100/1024)): #go for a few seconds
    data = np.fromstring(stream.read(CHUNK),dtype=np.int16)
    lastpeak = peak
    peak = np.average(np.abs(data))*peakMult/100
    bars = "#"*int(200*peak/2**16)

    #sine waves which control the color fade
    RedPinMult = ((math.cos(.01 * i + .1)) + 1) / 2
    GreenPinMult = (((math.cos(.027 * i + 1.571)) + 1) / 2)*.5
    BluePinMult = (((math.cos(.02 * i + 1.571)) + 1) / 2)*.5

    print("%04d %03d %.3f %.3f %.3f %s"%
    (i,peak,RedPinMult,GreenPinMult,BluePinMult,bars))

    #smoothing
    peakchange = np.abs(lastpeak-peak)
    if peakchange > 10:
        print("AYYYYYYYYYYYYYYYYY")
	#if increasing volume
	#if peak > lastpeak:
	    #peak = lastpeak + (peakchange-10)
	#else:
    	#peak = lastpeak - (peakchange-10)

    if peak < 100:
        RedPin.ChangeDutyCycle(peak * RedPinMult)
        GreenPin.ChangeDutyCycle(peak * GreenPinMult)
        BluePin.ChangeDutyCycle(peak * BluePinMult)


stream.stop_stream()
stream.close()
p.terminate()
RedPin.stop()
GreenPin.stop()
BluePin.stop()
GPIO.cleanup()
