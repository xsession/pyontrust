"""QtCore sub-module shim — re-exports everything from the parent package."""
from _pyside6_shim import (
    QCoreApplication,
    QObject,
    QLocale,
    QRect,
    Signal,
)
from _pyside6_shim import _QtCore
qRegisterResourceData = _QtCore.qRegisterResourceData
qUnregisterResourceData = _QtCore.qUnregisterResourceData
