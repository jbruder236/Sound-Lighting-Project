#!/usr/bin/env python3
# rpi_ws281x library
# Author: James Bruder
#
# Using ws281x light strip and pyaudio
# Based off strandtest.py example of ws281x library

# 10/24 Patch Notes:
# -
# -

# Light Pattern ideas:
# -Pulse across length of strip (what is the trigger?)
# -

import pyaudio
import time
import numpy as np
import math
from rpi_ws281x import *
import argparse

# LED strip configuration:
LED_COUNT      = 100      # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

####################################################################
#PyAudio Config:
peakMult = .55 #multiplier for the volume variable "peak"
CHUNK = 2**11
RATE = 88200
#RATE = 44100 - Alternative Rate
p=pyaudio.PyAudio()

stream=p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK
)

peak = 0
# My Function Animations:
def soundLight(strip, wait_ms=20):
    maxDelta = 5
    lastPeak = 0
    maxPeak = 0 #tracking max peak after limit correction
    avgPeak = 0
    totalPeak = 0
    totalTime = 0
    for i in range(256*20):
        iTime = time.time()

        #Audio Sampling:
        data = np.fromstring(stream.read(CHUNK),dtype=np.int16)
        peak = np.average(np.abs(data))*peakMult/100
        peakDelta = peak-lastPeak
        bars = "#"*int(peak/10)
        print("i:%04d  peak:%03d  maxPeak:%03d  avgPeak:%03d   %s"% (i, peak, maxPeak, avgPeak, bars))
        totalPeak += peak
        avgPeak = totalPeak / (i+1)

        if abs(peakDelta) > maxDelta:
            #if increasing peak
            if peak > lastPeak:
                peak = lastPeak + maxDelta
            if peak < lastPeak:
                peak = lastPeak - maxDelta
        if peak > maxPeak:
            maxPeak = peak
        if peak > 100:
            peak = 100
        if peak < 0:
            peak = 1
        #peak = 70

        #rainbow coloring
        for j in range(strip.numPixels()):
            strip.setPixelColor(j, wheel((j + i) & 255))
            #strip.setPixelColor(j, wheelminusgreen((j + i) & 255))
            #strip.setPixelColor(j, fallwheel((j + i) & 255))
            #strip.setPixelColor(j, Color(90, 0, 255))

        brightSet = math.floor(peak*1.5)
        strip.setBrightness(brightSet)
        strip.show()
        lastPeak = peak

        fTime = time.time()
#Use block below and place iTime/fTime in loop to selectively measure processes
        iterTime = fTime-iTime
        totalTime += iterTime
        avgTime = totalTime / (i+1)
        #print("Iteration Time: %.5f  AIT: %.4f"% (iterTime, avgTime))


# Default functions which animate LEDs in various ways:
def colorWipe(strip, color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)

def theaterChase(strip, color, wait_ms=50, iterations=10):
    """Movie theater light style chaser animation."""
    for j in range(iterations):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, color)
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)

def wheelminusgreen(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 0, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, 0, 255 - pos * 3)

#fall colors
def fallwheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(0, int(math.floor((255 - pos * 3)/2)), 255 - pos * 3)
    elif pos < 170:
        pos -= 85
        return Color(0, int(math.floor((pos * 3)/4)), pos * 3)
    else:
        pos -= 170
        return Color(0, 0, 255 - pos * 3)

def rainbow(strip, wait_ms=20, iterations=1):
    """Draw rainbow that fades across all pixels at once."""
    for j in range(256*iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((i+j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)

def rainbowCycle(strip, wait_ms=20, iterations=5):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    for j in range(256*iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
        strip.show()
        time.sleep(wait_ms/1000.0)

def theaterChaseRainbow(strip, wait_ms=50):
    """Rainbow movie theater light style chaser animation."""
    for j in range(256):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, wheel((i+j) % 255))
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

# Main program logic follows:
if __name__ == '__main__':
    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
    args = parser.parse_args()

    # Create NeoPixel object with appropriate configuration.
    strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    # Intialize the library (must be called once before other functions).
    strip.begin()

    print ('Press Ctrl-C to quit.')
    if not args.clear:
        print('Use "-c" argument to clear LEDs on exit')

    try:

        while True:
            print('Sound Lighting...')
            soundLight(strip)


    except KeyboardInterrupt:
        if args.clear:
            colorWipe(strip, Color(0,0,0), 10)
