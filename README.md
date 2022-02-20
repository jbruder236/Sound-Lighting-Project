# Sound-Lighting-Project

This has been an ongoing personal project for me since my first semester at UConn. There have been multiple versions of code, along with multiple versions of hardware. The light strips I've used have had different protocols but the fundamental idea has been the same: sound-reactive lighting via a programmed microcontroller.

### Using a Raspberry Pi:
  -Analyze sound input via aux using python
  -Control light strip with python
  -Use the sound data to control the light strip in real-time for a colorful display that matches the music
  
I now use a WS2811 LED light strip. This strip has the advantage of being addressable. This means that individual LEDs (or groups of LEDs) can be individually/separately controlled.

### Future Ideas/Improvements:
  -Integrate with guitar amp to play music with reactive lighting (COMPLETED)
  -Use FFTs to analyze the music by frequency-domain in real-time for pitch-reactive lighting (Currently In Development/Testing)
