# analogin.py

import random
from .constants import DwfStateDone

def FDwfAnalogInConfigure(hdwf, fReconfigure, fStart):
    return 1

def FDwfAnalogInStatus(hdwf, fReadData, psts):
    psts[0] = DwfStateDone
    return 1

def FDwfAnalogInStatusData(hdwf, idxChannel, rgdVoltData, cdData):
    for i in range(cdData):
        rgdVoltData[i] = random.uniform(-5.0, 5.0)
    return 1
