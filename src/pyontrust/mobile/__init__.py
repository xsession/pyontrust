"""Mobile-device subsystems: acoustic arrays, stereo-3D tracking, spectroscopy.

These modules target Android phones (Termux/ADB bridges) and companion
hardware. They are optional — install the matching extra for each domain::

    pip install pyontrust[acoustics]      # beamforming / noise localization
    pip install pyontrust[stereo3d]       # dual-camera 3D tracking
    pip install pyontrust[spectroscopy]   # phone spectrometer pipeline
"""
