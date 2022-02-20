#https://makersportal.com/blog/2018/9/20/audio-processing-in-python-part-iii-guitar-string-theory-and-frequency-analysis
#Code Performs the following steps:
#1. Record 1 second of audio data using a USB mic
#2. Subtract background noise in time and spectral domain
#3. Calculate FFT for guitar strum
#4. Plot frequency spectra of guitar strum
#5. Annotate 6 peak frequencies related using a peak finding algorithm
#I only added runtime analysis

import pyaudio
import matplotlib.pyplot as plt
import numpy as np
import time

plt.style.use('ggplot')

form_1 = pyaudio.paInt16 # 16-bit resolution
chans = 1 # 1 channel
samp_rate = 44100 # 44.1kHz sampling rate
chunk = 1024*2 # samples for buffer (more samples = better freq resolution)

audio = pyaudio.PyAudio() # create pyaudio instantiation

# mic sensitivity correction and bit conversion
mic_sens_dBV = -47.0 # mic sensitivity in dBV + any gain
mic_sens_corr = np.power(10.0,mic_sens_dBV/20.0) # calculate mic sensitivity conversion factor

# compute FFT parameters
f_vec = samp_rate*np.arange(chunk/2)/chunk # frequency vector based on window size and sample rate

# prepare plot for live updating
plt.figure(1)
plt.ion()
fig = plt.figure(figsize=(12,5))
ax = fig.add_subplot(111)
y = np.zeros((int(np.floor(chunk/2)),1))
line1, = ax.plot(f_vec,y)
plt.xlabel('Frequency [Hz]',fontsize=22)
plt.ylabel('Amplitude [Pa]',fontsize=22)
plt.grid(True)
plt.annotate(r'Delta f_{max}$: %2.1f Hz' % (samp_rate/(2*chunk)),xy=(0.7,0.9),xycoords='figure fraction',fontsize=16)
ax.set_xscale('log')
ax.set_xlim([1,0.8*samp_rate])
plt.pause(0.0001)

# create pyaudio stream
stream = audio.open(format = form_1,rate = samp_rate,channels = chans, input = True, frames_per_buffer=chunk)

avg_freq_brackets = []

iterations = 15
# loop through stream and look for dominant peaks while also subtracting noise
for iteration in range(iterations):
    itime = time.time()
    # read stream and convert data from bits to Pascals
    stream.start_stream()
    data = np.frombuffer(stream.read(chunk),dtype=np.int16)
    data = ((data/np.power(2.0,15))*5.25)*(mic_sens_corr)
    stream.stop_stream()

    samptime = time.time() - itime

    # compute FFT
    fft_data = (np.abs(np.fft.fft(data))[0:int(np.floor(chunk/2))])/chunk
    fft_data[1:] = 2*fft_data[1:]

    fftime = time.time() - itime - samptime

    # plot the new data and adjust y-axis (if needed)
    line1.set_ydata(fft_data)
    if np.max(fft_data)>(ax.get_ylim())[1] or np.max(fft_data)<0.5*((ax.get_ylim())[1]):
        ax.set_ylim([0,1.2*np.max(fft_data)])

    #map array of length 1024 (fft_data) into array of length n (n brackets)
    #use friture to decide buckets
    #edit frequency bracket bounds until approx equal magnitudes
    #what colors blend well?
    freq_bracket = np.empty(4, dtype=np.dtype(float))
    bucket = 0
    bracketbuster = 100000
    for i in range(len(fft_data)):
        if(i%256 == 0 and i != 0):
            bucket+=1
            freq_bracket[bucket] += fft_data[i]
        else:
            freq_bracket[bucket] += fft_data[i]
            #print(i, bucket, fft_data[i])
    #print(np.argmax(fft_data))
    plt.plot(fft_data, color="blue")

    avg_freq_brackets.append(freq_bracket)


    plt.pause(.1)
    plottime = time.time() - itime - fftime - samptime
    totaltime = time.time() - itime
    print("Sample Time: %.4f      FFT Time: %.4f     Plot Time: %.4f        Total Time: %.4f"%(samptime, fftime, plottime, totaltime))

    if(iteration == iterations-1):
        totals = [0.0]*4
        for i in range(len(avg_freq_brackets)):
            totals[0] += avg_freq_brackets[i][0]
            totals[1] += avg_freq_brackets[i][1]
            totals[2] += avg_freq_brackets[i][2]
            totals[3] += avg_freq_brackets[i][3]
        for i in range(len(totals)):
            totals[i] = totals[i] / len(avg_freq_brackets)
        print(totals)
