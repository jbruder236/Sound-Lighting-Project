#https://makersportal.com/blog/2018/9/20/audio-processing-in-python-part-iii-guitar-string-theory-and-frequency-analysis
#Code Performs the following steps:
#1. Record 1 second of audio data using a USB mic
#2. Subtract background noise in time and spectral domain
#3. Calculate FFT for guitar strum
#4. Plot frequency spectra of guitar strum
#5. Annotate 6 peak frequencies related using a peak finding algorithm

#This version of GSA runs a continuous loop and noise corrects once in INIT stage

import pyaudio
import numpy as np
import time

form_1 = pyaudio.paInt16 # 16-bit resolution
chans = 1 # 1 channel
samp_rate = 44100 # 44.1kHz sampling rate
chunk = 1024*10 # samples for buffer (more samples = better freq resolution)

audio = pyaudio.PyAudio() # create pyaudio instantiation

# mic sensitivity correction and bit conversion
mic_sens_dBV = -47.0 # mic sensitivity in dBV + any gain
mic_sens_corr = np.power(10.0,mic_sens_dBV/20.0) # calculate mic sensitivity conversion factor

# compute FFT parameters
f_vec = samp_rate*np.arange(chunk/2)/chunk # frequency vector based on window size and sample rate
mic_low_freq = 70 # low frequency response of the mic (mine in this case is 100 Hz)
low_freq_loc = np.argmin(np.abs(f_vec-mic_low_freq))

# create pyaudio stream
stream = audio.open(format = form_1,rate = samp_rate,channels = chans, input = True, frames_per_buffer=chunk)

# some peak-finding and noise preallocations
peak_shift = 5
noise_fft_vec,noise_amp_vec = [],[]
peak_data = []

noise_len = 5
#INIT Setup of Noise Correction
for ii in range(noise_len):
    if(ii == 0):
        print("Stay Quiet, Measuring Noise...")
    else:
        print("...")
    stream.start_stream()
    data = np.frombuffer(stream.read(chunk),dtype=np.int16)
    data = ((data/np.power(2.0,15))*5.25)*(mic_sens_corr)
    stream.stop_stream()

    fft_data = (np.abs(np.fft.fft(data))[0:int(np.floor(chunk/2))])/chunk
    fft_data[1:] = 2*fft_data[1:]

    noise_fft_vec.append(fft_data)
    noise_amp_vec.extend(data)

    if ii==noise_len-1:
        noise_fft = np.max(noise_fft_vec,axis=0)
        noise_amp = np.mean(noise_amp_vec)
        print("Noise Correction Complete.")

# loop through stream and look for dominant peaks while also subtracting noise
while True:
    itime = time.time()
    # read stream and convert data from bits to Pascals
    stream.start_stream()
    data = np.frombuffer(stream.read(chunk),dtype=np.int16)
    data = data-noise_amp   #noise correction
    data = ((data/np.power(2.0,15))*5.25)*(mic_sens_corr)
    stream.stop_stream()

    samptime = time.time() - itime

    # compute FFT
    fft_data = (np.abs(np.fft.fft(data))[0:int(np.floor(chunk/2))])/chunk
    fft_data[1:] = 2*fft_data[1:]

    fftime = time.time() - itime - samptime

    fft_data = np.subtract(fft_data,noise_fft) # subtract average spectral noise



    # annotate peak frequencies (6 largest peaks, max width of 10 Hz [can be controlled by peak_shift above])
    peak_data = 1.0*fft_data
    peak_freqs = []
    for jj in range(6):
        max_loc = np.argmax(peak_data[low_freq_loc:])
        if peak_data[max_loc+low_freq_loc]>10*np.mean(noise_amp):
            peak_freqs.append(f_vec[max_loc+low_freq_loc])
            # zero-out old peaks so we dont find them again
            peak_data[max_loc+low_freq_loc-peak_shift:max_loc+low_freq_loc+peak_shift] = np.repeat(0,peak_shift*2)

    print(peak_freqs)
    totaltime = time.time() - itime
    print("Sample Time: %.4f      FFT Time: %.4f    Total Time: %.4f"%(samptime, fftime, totaltime))
