"""Device orchestration: ADB management + Termux camera/mic bridges."""
from .adb_manager import ADBManager, DeviceInfo
from .termux_bridge import TermuxBridge, CameraConfig

__all__ = ["ADBManager", "DeviceInfo", "TermuxBridge", "CameraConfig"]
