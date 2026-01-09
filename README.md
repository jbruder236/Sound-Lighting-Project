# Sound-Lighting-Project

### Modern RPi Setup:
1. Enable I2C and SPI via `sudo raspi-config`
2. `sudo apt install -y python3-pyaudio`
3. `sudo apt install -y python3-numpy`
4.  `sudo pip3 install rpi_ws281x --break-system-packages`

### Notes:
- Sound input via aux sound card
- Control light strip with Python
  
For WS2811 LED light strip w/ addressable LEDS.

### Planned:
- Use FFTs to analyze by frequency-domain in real-time for pitch-reactive lighting
