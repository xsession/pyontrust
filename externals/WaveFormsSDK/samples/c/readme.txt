Building the examples under different systems:

Windows Visual Studio 2013:
  - File / New Project / Win32 Console Application / Next / select Console Application and check Empty project / Finish
  - Copy C:\Program Files (x86)\Digilent\WaveFormsSDK\samples\c\device_enumeration.c and sample.h to your project folder.
  - Copy C:\Program Files (x86)\Digilent\WaveFormsSDK\lib\x86\dwf.lib (or from x64 for 64bit application) to your project folder.
  - Add Existing Items/ device_enumeration.cpp, samples.h, dwf.h
  - Edit samples.h, change the #include "../../inc/dwf.h" to #include "dwf.h"
  - Under Project / Properties / Linker / Input / Additional Dependencies / add "dwf.lib"
  
Linux from terminal:
  - make sure to install Digilent Adept Runtime too
  - compile with:
    gcc /usr/share/digilent/waveforms/samples/c/device_enumeration.cpp -ldwf -o device_enumeration.out

Linux Code::Blocks IDE:
  - File / New Project / Console application / Go / Next / C++ / Next /...
  - Copy /usr/share/digilent/waveforms/samples/c/samples.h, device_enumeration.cpp to your project folder.
  - Project / Add files / 
  - Project / Build options / Linker Settings / Add / enter: "dwf"

OS X:
  - install the dwf.framework from the disk image to the /Library/Frameworks
  - compile with:
    gcc /Applications/WaveForms.app/Contents/Resources/SDK/samples/c/device_enumeration.cpp -F /Library/Frameworks -framework dwf -o device_enumeration.out
