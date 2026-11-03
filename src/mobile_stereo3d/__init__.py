"""mobile_stereo3d — multi-phone stereoscopic 3-D acquisition & tracking.

Turns two (or more) Android phone cameras controlled from a PC via Termux +
ADB into a synchronized multi-view / stereoscopic 3-D system:

    controller/     ADB orchestration + Termux camera/mic bridges
    sync/           frame streams + timestamp matching
    calibration/    intrinsics/extrinsics + epipolar rectification
    reconstruction/ 2-D localization + 3-D triangulation
    tracking/       time-series 3-D trajectories + CSV/JSON/PLY export
    utils/          3-D visualization

Example (design-doc workflow)::

    from mobile_stereo3d.controller import ADBManager, TermuxBridge
    from mobile_stereo3d.sync import StreamSynchronizer
    from mobile_stereo3d.calibration import StereoCalibrator
    from mobile_stereo3d.reconstruction import Triangulator
    from mobile_stereo3d.tracking import Tracker3D

    adb = ADBManager()
    cam1 = TermuxBridge(device_id=adb.get_device(0).serial, port=8081)
    calib = StereoCalibrator().from_baseline(K_left, D_left, baseline_px=120)
    tri = Triangulator(calib)
    tracker = Tracker3D()
"""

from .controller import ADBManager, DeviceInfo, TermuxBridge
from .sync import FrameStream, StreamSynchronizer
from .calibration import StereoCalibration, StereoCalibrator, StereoRectifier
from .reconstruction import FeatureLocalizer, Triangulator
from .tracking import Tracker3D, Track
from .utils import Visualizer3D

__version__ = "0.1.0"
