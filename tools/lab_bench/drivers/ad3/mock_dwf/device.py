# device.py

from .constants import hdwfNone
from . import errors

_next_handle = 1
_devices_opened = {}

def FDwfDeviceOpen(idxDevice, phdwf):
    global _next_handle
    handle = _next_handle
    _devices_opened[handle] = True
    _next_handle += 1
    phdwf[0] = handle
    return 1

def FDwfDeviceClose(hdwf):
    _devices_opened.pop(hdwf, None)
    return 1

def FDwfGetVersion(szVersion):
    szVersion[:] = b"3.16.4"
    return 1
