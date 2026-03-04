from __future__ import annotations

import os
import sys
from ctypes import (
    POINTER,
    byref,
    c_char,
    c_double,
    c_int,
    c_ubyte,
    create_string_buffer,
)
from ctypes.util import find_library
from dataclasses import dataclass

import ctypes

from ...errors import FfiCallFailed


HDWF = c_int  # DWF uses int handles
BOOL = c_int

# Selected constants from dwf.h
enumfilterAll = 0

trigsrcNone = 0
trigsrcPC = 1
trigsrcDetectorAnalogIn = 2

DwfTriggerSlopeRise = 0
DwfTriggerSlopeFall = 1

DwfStateReady = 0
DwfStateArmed = 1
DwfStateDone = 2
DwfStateTriggered = 3

acqmodeSingle = 0
acqmodeRecord = 3


def _default_lib_name() -> str:
    if sys.platform.startswith("win"):
        return "dwf.dll"
    if sys.platform.startswith("linux"):
        return "libdwf.so"
    return "dwf"


def load_dwf_library() -> ctypes.CDLL:
    override = os.environ.get("PYONTRUST_DWF_LIB")
    candidates = [override] if override else []
    candidates.append(_default_lib_name())

    if not override:
        found = find_library("dwf")
        if found:
            candidates.append(found)

    last_err: Exception | None = None
    for name in [c for c in candidates if c]:
        try:
            return ctypes.CDLL(name)
        except Exception as e:
            last_err = e
    raise FfiCallFailed(f"Failed to load WaveForms DWF library. Tried: {candidates}. Error: {last_err}")


@dataclass
class DwfFns:
    lib: ctypes.CDLL

    # Common
    DwfGetLastErrorMsg: any

    # Discovery/open
    DwfEnum: any
    DwfEnumDeviceName: any
    DwfDeviceOpen: any
    DwfDeviceClose: any

    # AnalogIn
    DwfAnalogInFrequencySet: any
    DwfAnalogInBufferSizeSet: any
    DwfAnalogInRecordLengthSet: any
    DwfAnalogInAcquisitionModeSet: any
    DwfAnalogInChannelEnableSet: any
    DwfAnalogInChannelRangeSet: any
    DwfAnalogInChannelOffsetSet: any
    DwfAnalogInTriggerSourceSet: any
    DwfAnalogInTriggerTypeSet: any
    DwfAnalogInTriggerChannelSet: any
    DwfAnalogInTriggerPositionSet: any
    DwfAnalogInTriggerHoldOffSet: any
    DwfAnalogInTriggerAutoTimeoutSet: any
    DwfAnalogInTriggerLevelSet: any
    DwfAnalogInTriggerConditionSet: any
    DwfAnalogInTriggerHysteresisSet: any
    DwfAnalogInConfigure: any
    DwfAnalogInStatus: any
    DwfAnalogInStatusSamplesValid: any
    DwfAnalogInStatusIndexWrite: any
    DwfAnalogInStatusRecord: any
    DwfAnalogInStatusData: any
    DwfAnalogInStatusData2: any

    # AnalogOut (minimal)
    DwfAnalogOutEnableSet: any
    DwfAnalogOutFunctionSet: any
    DwfAnalogOutFrequencySet: any
    DwfAnalogOutAmplitudeSet: any
    DwfAnalogOutOffsetSet: any
    DwfAnalogOutRunSet: any
    DwfAnalogOutConfigure: any


def bind_dwf(lib: ctypes.CDLL) -> DwfFns:
    # Common
    lib.FDwfGetLastErrorMsg.argtypes = [POINTER(c_char)]
    lib.FDwfGetLastErrorMsg.restype = None

    # Discovery
    lib.FDwfEnum.argtypes = [c_int, POINTER(c_int)]
    lib.FDwfEnum.restype = BOOL

    lib.FDwfEnumDeviceName.argtypes = [c_int, POINTER(c_char)]
    lib.FDwfEnumDeviceName.restype = BOOL

    lib.FDwfDeviceOpen.argtypes = [c_int, POINTER(HDWF)]
    lib.FDwfDeviceOpen.restype = BOOL

    lib.FDwfDeviceClose.argtypes = [HDWF]
    lib.FDwfDeviceClose.restype = BOOL

    # AnalogIn
    lib.FDwfAnalogInFrequencySet.argtypes = [HDWF, c_double]
    lib.FDwfAnalogInFrequencySet.restype = BOOL

    lib.FDwfAnalogInBufferSizeSet.argtypes = [HDWF, c_int]
    lib.FDwfAnalogInBufferSizeSet.restype = BOOL

    lib.FDwfAnalogInRecordLengthSet.argtypes = [HDWF, c_double]
    lib.FDwfAnalogInRecordLengthSet.restype = BOOL

    lib.FDwfAnalogInAcquisitionModeSet.argtypes = [HDWF, c_int]
    lib.FDwfAnalogInAcquisitionModeSet.restype = BOOL

    lib.FDwfAnalogInChannelEnableSet.argtypes = [HDWF, c_int, BOOL]
    lib.FDwfAnalogInChannelEnableSet.restype = BOOL

    lib.FDwfAnalogInChannelRangeSet.argtypes = [HDWF, c_int, c_double]
    lib.FDwfAnalogInChannelRangeSet.restype = BOOL

    lib.FDwfAnalogInChannelOffsetSet.argtypes = [HDWF, c_int, c_double]
    lib.FDwfAnalogInChannelOffsetSet.restype = BOOL

    lib.FDwfAnalogInTriggerSourceSet.argtypes = [HDWF, c_ubyte]
    lib.FDwfAnalogInTriggerSourceSet.restype = BOOL

    lib.FDwfAnalogInTriggerTypeSet.argtypes = [HDWF, c_int]
    lib.FDwfAnalogInTriggerTypeSet.restype = BOOL

    lib.FDwfAnalogInTriggerChannelSet.argtypes = [HDWF, c_int]
    lib.FDwfAnalogInTriggerChannelSet.restype = BOOL

    lib.FDwfAnalogInTriggerPositionSet.argtypes = [HDWF, c_double]
    lib.FDwfAnalogInTriggerPositionSet.restype = BOOL

    lib.FDwfAnalogInTriggerHoldOffSet.argtypes = [HDWF, c_double]
    lib.FDwfAnalogInTriggerHoldOffSet.restype = BOOL

    lib.FDwfAnalogInTriggerAutoTimeoutSet.argtypes = [HDWF, c_double]
    lib.FDwfAnalogInTriggerAutoTimeoutSet.restype = BOOL

    lib.FDwfAnalogInTriggerLevelSet.argtypes = [HDWF, c_double]
    lib.FDwfAnalogInTriggerLevelSet.restype = BOOL

    lib.FDwfAnalogInTriggerConditionSet.argtypes = [HDWF, c_int]
    lib.FDwfAnalogInTriggerConditionSet.restype = BOOL

    lib.FDwfAnalogInTriggerHysteresisSet.argtypes = [HDWF, c_double]
    lib.FDwfAnalogInTriggerHysteresisSet.restype = BOOL

    lib.FDwfAnalogInConfigure.argtypes = [HDWF, BOOL, BOOL]
    lib.FDwfAnalogInConfigure.restype = BOOL

    lib.FDwfAnalogInStatus.argtypes = [HDWF, BOOL, POINTER(c_ubyte)]
    lib.FDwfAnalogInStatus.restype = BOOL

    lib.FDwfAnalogInStatusSamplesValid.argtypes = [HDWF, POINTER(c_int)]
    lib.FDwfAnalogInStatusSamplesValid.restype = BOOL

    lib.FDwfAnalogInStatusIndexWrite.argtypes = [HDWF, POINTER(c_int)]
    lib.FDwfAnalogInStatusIndexWrite.restype = BOOL

    lib.FDwfAnalogInStatusRecord.argtypes = [HDWF, POINTER(c_int), POINTER(c_int), POINTER(c_int)]
    lib.FDwfAnalogInStatusRecord.restype = BOOL

    lib.FDwfAnalogInStatusData.argtypes = [HDWF, c_int, POINTER(c_double), c_int]
    lib.FDwfAnalogInStatusData.restype = BOOL

    lib.FDwfAnalogInStatusData2.argtypes = [HDWF, c_int, POINTER(c_double), c_int, c_int]
    lib.FDwfAnalogInStatusData2.restype = BOOL

    # AnalogOut
    lib.FDwfAnalogOutEnableSet.argtypes = [HDWF, c_int, BOOL]
    lib.FDwfAnalogOutEnableSet.restype = BOOL

    lib.FDwfAnalogOutFunctionSet.argtypes = [HDWF, c_int, c_int]
    lib.FDwfAnalogOutFunctionSet.restype = BOOL

    lib.FDwfAnalogOutFrequencySet.argtypes = [HDWF, c_int, c_double]
    lib.FDwfAnalogOutFrequencySet.restype = BOOL

    lib.FDwfAnalogOutAmplitudeSet.argtypes = [HDWF, c_int, c_double]
    lib.FDwfAnalogOutAmplitudeSet.restype = BOOL

    lib.FDwfAnalogOutOffsetSet.argtypes = [HDWF, c_int, c_double]
    lib.FDwfAnalogOutOffsetSet.restype = BOOL

    lib.FDwfAnalogOutRunSet.argtypes = [HDWF, c_int, c_double]
    lib.FDwfAnalogOutRunSet.restype = BOOL

    lib.FDwfAnalogOutConfigure.argtypes = [HDWF, c_int, BOOL]
    lib.FDwfAnalogOutConfigure.restype = BOOL

    return DwfFns(
        lib=lib,
        DwfGetLastErrorMsg=lib.FDwfGetLastErrorMsg,
        DwfEnum=lib.FDwfEnum,
        DwfEnumDeviceName=lib.FDwfEnumDeviceName,
        DwfDeviceOpen=lib.FDwfDeviceOpen,
        DwfDeviceClose=lib.FDwfDeviceClose,
        DwfAnalogInFrequencySet=lib.FDwfAnalogInFrequencySet,
        DwfAnalogInBufferSizeSet=lib.FDwfAnalogInBufferSizeSet,
        DwfAnalogInRecordLengthSet=lib.FDwfAnalogInRecordLengthSet,
        DwfAnalogInAcquisitionModeSet=lib.FDwfAnalogInAcquisitionModeSet,
        DwfAnalogInChannelEnableSet=lib.FDwfAnalogInChannelEnableSet,
        DwfAnalogInChannelRangeSet=lib.FDwfAnalogInChannelRangeSet,
        DwfAnalogInChannelOffsetSet=lib.FDwfAnalogInChannelOffsetSet,
        DwfAnalogInTriggerSourceSet=lib.FDwfAnalogInTriggerSourceSet,
        DwfAnalogInTriggerTypeSet=lib.FDwfAnalogInTriggerTypeSet,
        DwfAnalogInTriggerChannelSet=lib.FDwfAnalogInTriggerChannelSet,
        DwfAnalogInTriggerPositionSet=lib.FDwfAnalogInTriggerPositionSet,
        DwfAnalogInTriggerHoldOffSet=lib.FDwfAnalogInTriggerHoldOffSet,
        DwfAnalogInTriggerAutoTimeoutSet=lib.FDwfAnalogInTriggerAutoTimeoutSet,
        DwfAnalogInTriggerLevelSet=lib.FDwfAnalogInTriggerLevelSet,
        DwfAnalogInTriggerConditionSet=lib.FDwfAnalogInTriggerConditionSet,
        DwfAnalogInTriggerHysteresisSet=lib.FDwfAnalogInTriggerHysteresisSet,
        DwfAnalogInConfigure=lib.FDwfAnalogInConfigure,
        DwfAnalogInStatus=lib.FDwfAnalogInStatus,
        DwfAnalogInStatusSamplesValid=lib.FDwfAnalogInStatusSamplesValid,
        DwfAnalogInStatusIndexWrite=lib.FDwfAnalogInStatusIndexWrite,
        DwfAnalogInStatusRecord=lib.FDwfAnalogInStatusRecord,
        DwfAnalogInStatusData=lib.FDwfAnalogInStatusData,
        DwfAnalogInStatusData2=lib.FDwfAnalogInStatusData2,
        DwfAnalogOutEnableSet=lib.FDwfAnalogOutEnableSet,
        DwfAnalogOutFunctionSet=lib.FDwfAnalogOutFunctionSet,
        DwfAnalogOutFrequencySet=lib.FDwfAnalogOutFrequencySet,
        DwfAnalogOutAmplitudeSet=lib.FDwfAnalogOutAmplitudeSet,
        DwfAnalogOutOffsetSet=lib.FDwfAnalogOutOffsetSet,
        DwfAnalogOutRunSet=lib.FDwfAnalogOutRunSet,
        DwfAnalogOutConfigure=lib.FDwfAnalogOutConfigure,
    )


class DwfSafe:
    def __init__(self) -> None:
        self._lib = load_dwf_library()
        self.f = bind_dwf(self._lib)

    def last_error(self) -> str:
        buf = create_string_buffer(512)
        self.f.DwfGetLastErrorMsg(buf)
        return buf.value.decode(errors="replace")

    def _ok(self, ok: int, what: str) -> None:
        if int(ok) == 0:
            raise FfiCallFailed(f"DWF call failed: {what}. LastError: {self.last_error()}")

    def enum_devices(self) -> list[tuple[int, str]]:
        count = c_int()
        self._ok(self.f.DwfEnum(enumfilterAll, byref(count)), "DwfEnum")
        out: list[tuple[int, str]] = []
        for idx in range(int(count.value)):
            name = create_string_buffer(64)
            self._ok(self.f.DwfEnumDeviceName(idx, name), "DwfEnumDeviceName")
            out.append((idx, name.value.decode(errors="replace")))
        return out
