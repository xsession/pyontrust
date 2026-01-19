import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT / "pyontrust_packages"))

from power_test_framework.instruments import dwf_loader  # noqa: E402


class TestDwfLoader(unittest.TestCase):
    def test_find_dwf_library_prefers_env_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            fake = tmp_path / "dwf.dll"
            fake.write_bytes(b"not a real dll")

            lib = dwf_loader.find_dwf_library(
                platform="win32",
                env={"DWF_LIB_PATH": str(fake), "ProgramFiles": str(tmp_path), "ProgramFiles(x86)": str(tmp_path)},
                repo_root=tmp_path,
            )
            self.assertEqual(lib, fake)

    def test_find_dwf_library_linux_uses_repo_vendor_path_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            vendored = tmp_path / "externals" / "WaveformSDK_linux" / "usr" / "lib"
            vendored.mkdir(parents=True, exist_ok=True)
            fake = vendored / "libdwf.so"
            fake.write_bytes(b"not a real so")

            lib = dwf_loader.find_dwf_library(platform="linux", env={}, repo_root=tmp_path)
            self.assertEqual(lib, fake)


if __name__ == "__main__":
    unittest.main()
