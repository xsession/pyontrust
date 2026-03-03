"""PySide6 shim — provides *just enough* stubs so baramFlow's non-GUI code
can be imported in a headless (Flask) environment without the real Qt library.

Baram's CoreDB layer transitively imports two PySide6 symbols:
  1. resource_rc.py         → ``from PySide6 import QtCore``
  2. baramFlow/coredb/libdb → ``from PySide6.QtCore import QCoreApplication``

Both only use QtCore for the Qt resource system and QCoreApplication.translate().
This shim replaces them with no-ops so everything else works unchanged.
"""


class _QCoreApplication:
    """Stub — ``translate(ctx, text)`` simply returns the text as-is."""

    @staticmethod
    def translate(context: str, text: str, *args, **kwargs) -> str:
        return text

    @staticmethod
    def instance():
        return None


class _QLocale:
    """Stub for QLocale (used by app_settings.py)."""
    def __init__(self, *a, **kw):
        pass
    def name(self):
        return "C"
    @staticmethod
    def system():
        return _QLocale()


class _QRect:
    """Stub for QRect (used by app_settings.py)."""
    def __init__(self, *a):
        self._args = a
    def x(self): return 0
    def y(self): return 0
    def width(self): return 800
    def height(self): return 600


class _Signal:
    """Stub for PySide6.QtCore.Signal — becomes a no-op descriptor."""
    def __init__(self, *args, **kwargs):
        self._callbacks = []
    def connect(self, cb):
        self._callbacks.append(cb)
    def disconnect(self, cb=None):
        if cb:
            self._callbacks = [c for c in self._callbacks if c is not cb]
        else:
            self._callbacks.clear()
    def emit(self, *args):
        for cb in self._callbacks:
            try:
                cb(*args)
            except Exception:
                pass


class _QObject:
    """Stub QObject base — just enough for classes that inherit from it."""
    def __init__(self, *a, **kw):
        pass
    def tr(self, text, *a, **kw):
        return text


class _QtCore:
    """Namespace that mimics ``PySide6.QtCore``."""
    QCoreApplication = _QCoreApplication
    QObject = _QObject
    QLocale = _QLocale
    QRect = _QRect
    Signal = _Signal
    # resource_rc.py calls QtCore.qRegisterResourceData / qUnregisterResourceData
    @staticmethod
    def qRegisterResourceData(*a, **kw):
        return True
    @staticmethod
    def qUnregisterResourceData(*a, **kw):
        return True


# Module-level attributes so ``from PySide6 import QtCore`` works
QtCore = _QtCore

# Also expose so ``from PySide6.QtCore import X`` works
QCoreApplication = _QCoreApplication
QObject = _QObject
QLocale = _QLocale
QRect = _QRect
Signal = _Signal
