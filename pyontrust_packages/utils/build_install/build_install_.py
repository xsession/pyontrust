import os
import sys
import subprocess
import shutil
from pathlib import Path
import importlib.util
import ctypes
import logging
from datetime import datetime

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

try:
    # Works when executed as a module/package (e.g. `python -m build_install.build_install_`).
    import build_install.git_infos as git_infos
except ModuleNotFoundError:
    # Works when executed directly as a file (e.g. `python build_install_.py`).
    _this_dir = Path(__file__).resolve().parent
    if str(_this_dir) not in sys.path:
        sys.path.insert(0, str(_this_dir))
    import git_infos  # type: ignore

def rescource_path(relative_path):
    try:
        base_path = sys._MEIPASS
        print(f'base_path: {base_path}')
    except Exception:
        # Works for normal Python and Nuitka builds.
        # PyInstaller uses sys._MEIPASS; Nuitka does not.
        # For Nuitka onefile, __file__ typically resolves inside the extracted payload.
        base_path = Path(getattr(sys, "executable", __file__)).resolve().parent
        print(f'base_path: {base_path}')
    retval = Path(f'{base_path}/{relative_path}').resolve()
    return retval

def get_git_short_commit_hash(length=6):
    try:
        commit_hash = subprocess.check_output(
            ['git', 'rev-parse', f'--short={length}', 'HEAD']
        ).decode('utf-8').strip()
        return commit_hash
    except subprocess.CalledProcessError:
        return None

class AppBuilder:
    """
    A class to build a standalone application using Nuitka.
    """

    def __init__(self, app_name="YourAppName", app_path=None, main_script="main.py", debug_info=False, hide_console=False, dist_folder="dist", build_folder="build"):
        self.app_name = app_name
        self.app_path = app_path
        self.main_script = main_script
        self.hide_console = hide_console
        self.debug_info = debug_info
        self.version = None
        self.spec_file = None

        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_path = Path(__file__).parent
        self.dist_folder = os.path.join(base_path, f"build-{self.app_name}_{self.timestamp}/dist") if dist_folder == "dist" else dist_folder
        self.build_folder = os.path.join(base_path, f"build-{self.app_name}_{self.timestamp}/build") if build_folder == "build" else build_folder

        self.nuitka_cmd = []
        self.dependency_dirs = []

        # Nuitka build tuning (can be overridden by callers).
        # - jobs: controls parallel C compiler jobs. -1 means (CPU count - 1).
        self.jobs = -1
        # - use_ccache: enable compilation caching when ccache/clcache is available.
        self.use_ccache = True
        # - aggressive_includes: if True, force-include known dynamically-imported packages.
        #   If False, rely on normal import following to avoid compiling whole packages.
        self.aggressive_includes = False
        # Optional forced inclusions.
        self.force_include_packages = []
        self.force_include_modules = []
        # Data-only inclusions are cheap(er) than compiling whole packages.
        self.force_include_package_data = ["eel"]

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception as e:
            logger.error(f"Admin check failed: {e}")
            return False

    def check_nuitka(self):
        if importlib.util.find_spec("nuitka") is None:
            logger.error("Nuitka is not installed. Installing it with pip...")
            subprocess.run([sys.executable, "-m", "pip", "install", "nuitka"], check=True)
            logger.info("Nuitka installed successfully.")
            if importlib.util.find_spec("nuitka") is None:
                logger.error("Nuitka install completed but module still not importable.")
                return False
        return True

    def check_main_script(self):
        if not os.path.isfile(self.main_script):
            logger.error(f"Main script '{self.main_script}' does not exist.")
            return False
        return True

    def check_nuitka_in_path(self):
        # We execute Nuitka via `python -m nuitka` for interpreter correctness.
        return True

    def clean_previous_builds(self):
        logger.info("Cleaning up previous builds...")
        for path in [self.dist_folder, self.build_folder, self.spec_file]:
            if path and os.path.exists(path):
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)

    def _get_nuitka_output_root(self) -> Path:
        """Return a root output directory for Nuitka.

        Many Nuitka versions only support a single --output-dir for both
        intermediates and final output. We therefore compile into a common root
        and then place the final .exe into self.dist_folder.
        """
        dist_folder = Path(self.dist_folder).resolve()
        build_folder = Path(self.build_folder).resolve()
        try:
            return build_folder.parent
        except Exception:
            return dist_folder

    def _is_importable(self, module_name: str) -> bool:
        """Check if a module/package can be imported in this repo context."""
        try:
            mediso_packages_dir = Path(__file__).resolve().parents[1]
            original_sys_path = list(sys.path)
            if str(mediso_packages_dir) not in sys.path:
                sys.path.insert(0, str(mediso_packages_dir))
            return importlib.util.find_spec(module_name) is not None
        except Exception:
            return False
        finally:
            sys.path = original_sys_path

    def _maybe_add_include_package(self, package_name: str, include_data: bool = False) -> None:
        if self._is_importable(package_name):
            self.nuitka_cmd.append(f"--include-package={package_name}")
            if include_data:
                self.nuitka_cmd.append(f"--include-package-data={package_name}")
        else:
            logger.warning(f"Skipping Nuitka include-package '{package_name}' (not importable)")

    def _maybe_add_include_module(self, module_name: str) -> None:
        if self._is_importable(module_name):
            self.nuitka_cmd.append(f"--include-module={module_name}")
        else:
            logger.warning(f"Skipping Nuitka include-module '{module_name}' (not importable)")

    def _nuitka_add_data_arg(self, source_path: str, dest_name: str) -> list:
        src = Path(source_path)
        if src.is_dir():
            return [f"--include-data-dir={src}={dest_name}"]
        return [f"--include-data-files={src}={dest_name}"]

    def generate_nuitka_command(self):
        output_root = self._get_nuitka_output_root()

        # Nuitka is invoked as a module to guarantee using the intended interpreter.
        self.nuitka_cmd = [
            sys.executable,
            "-m",
            "nuitka",
            "--onefile",
            f"--output-dir={output_root}",
            f"--output-filename={self.app_name}",
            "--assume-yes-for-downloads",
            "--verbose",
            "--progress-bar=auto",
            "--show-memory",
            f"--jobs={self.jobs}",
        ]

        # Avoid "compile everything" unless needed.
        # If you hit missing-module issues due to dynamic imports, either:
        # - set app_builder.aggressive_includes = True
        # - or populate app_builder.force_include_packages/modules explicitly.
        if self.aggressive_includes:
            for package_name in ["eel", "serial", "pwtk", "canopen", "cantools", "can"]:
                self._maybe_add_include_package(package_name, include_data=True)
            for module_name in ["bottle_websocket", "websocket"]:
                self._maybe_add_include_module(module_name)
        else:
            for package_name in self.force_include_packages:
                self._maybe_add_include_package(package_name, include_data=False)
            for module_name in self.force_include_modules:
                self._maybe_add_include_module(module_name)
            for package_name in self.force_include_package_data:
                if self._is_importable(package_name):
                    self.nuitka_cmd.append(f"--include-package-data={package_name}")

        for dir_path, dir_name in self.dependency_dirs:
            self.nuitka_cmd.extend(self._nuitka_add_data_arg(dir_path, dir_name))

        if self.debug_info:
            # Helpful for troubleshooting missing imports/data.
            report_path = Path(self.build_folder).resolve().parent / "nuitka-report.xml"
            self.nuitka_cmd.append("--show-modules")
            self.nuitka_cmd.append("--show-scons")
            self.nuitka_cmd.append(f"--report={report_path}")

        if self.hide_console:
            self.nuitka_cmd.append("--windows-console-mode=disable")

        self.nuitka_cmd.append(self.main_script)
        logger.info(f"Nuitka command: {' '.join(map(str, self.nuitka_cmd))}")

    def run_nuitka(self):
        logger.info("Running Nuitka...")
        output_root = self._get_nuitka_output_root()

        env = os.environ.copy()
        # Make local repo packages importable for Nuitka (e.g. pwtk, cantools, canopen, ...)
        # They live under the workspace `mediso_packages/` folder and are typically imported
        # as top-level packages when that folder is on sys.path.
        mediso_packages_dir = Path(__file__).resolve().parents[1]
        existing_pythonpath = env.get("PYTHONPATH", "")
        if existing_pythonpath:
            env["PYTHONPATH"] = str(mediso_packages_dir) + os.pathsep + existing_pythonpath
        else:
            env["PYTHONPATH"] = str(mediso_packages_dir)

        # Enable compilation caching when possible.
        # Nuitka integrates with ccache/clcache when available; setting CCACHE_DIR
        # keeps the cache close to the build output and makes repeated builds faster.
        if self.use_ccache:
            if shutil.which("ccache") or shutil.which("clcache"):
                cache_dir = Path(self.build_folder).resolve().parent / "ccache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                env.setdefault("CCACHE_DIR", str(cache_dir))

        # Let Nuitka write directly to the console so its prompts and progress
        # bars render correctly (important for downloads / toolchain setup).
        proc = None
        try:
            proc = subprocess.Popen(
                self.nuitka_cmd,
                env=env,
            )
            returncode = proc.wait()
        except KeyboardInterrupt:
            logger.error("Build interrupted by user (Ctrl+C). Terminating Nuitka...")
            try:
                if proc is not None:
                    proc.terminate()
            except Exception:
                pass
            return False

        if returncode != 0:
            logger.error(f"Nuitka failed with exit code {returncode}.")
            return False

        # Put final artifact into the requested dist folder to keep the
        # existing dist/build folder structure stable for users.
        dist_dir = Path(self.dist_folder).resolve()
        dist_dir.mkdir(parents=True, exist_ok=True)

        expected_exe = output_root / f"{self.app_name}.exe"
        if expected_exe.exists():
            shutil.move(str(expected_exe), str(dist_dir / expected_exe.name))
        else:
            candidates = sorted(output_root.glob(f"{self.app_name}*.exe"))
            if candidates:
                shutil.move(str(candidates[0]), str(dist_dir / candidates[0].name))
            else:
                logger.warning(
                    f"Nuitka completed but no .exe found in output root: {output_root}"
                )

        logger.info("Nuitka completed successfully.")
        return True

    def get_version(self):
        if self.app_path is None:
            self.app_path = Path(__file__).parent
        version_path = Path(self.app_path) / self.main_script
        if version_path.exists():
            spec = importlib.util.spec_from_file_location("version", version_path)
            version_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(version_module)
            return getattr(version_module, "__version__", "unknown")
        return "unknown"

    # insert git info into the main script docstring but keep the original docstring because i use it for docopt
    # i place a placeholder in the docstring
    # and replace it with the git info
    # the placeholder is ########## ########## ########## and the git info will be inserted after it, 
    # but the modification will not overwrite the original docstring
    def insert_git_info(self):
        git_info = git_infos.GITInfo()
        commit_hash = git_info.commit_hash
        commit_date = git_info.commit_date
        branch = git_info.branch
        user_name = git_info.user_name
        user_email = git_info.user_email
        user = os.getenv("USERNAME") or os.getenv("USER")
        lines = []
        placeholder_index = None
        git_info_str = f"""
Commit hash: {commit_hash}
Full commit hash: {git_info.full_commit_hash}
Commit date: {commit_date}
Branch: {branch}
User name: {user_name}
User email: {user_email}
Logged-in user: {user}
        """
        
        with open(self.main_script, "r") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if "########## ########## ##########" in line:
                    placeholder_index = i
                    if "Commit hash:" in lines[i+2]:
                        for j in range(1, len(git_info_str.strip().splitlines()) + i):
                            lines.pop(i+2)
                    
                    lines.insert(i+1, git_info_str)
                    break
                
        with open(self.main_script, "w") as f:
            f.writelines(lines)

    def build_installer(self):
        self.version = self.get_version()
        if self.version == "unknown":
            logger.error(f"Version file not found or __version__ not defined. {self}")
            return

        self.app_name = f"{self.app_name}_v{self.version}_sha{git_infos.GITInfo().commit_hash}_{self.timestamp}"
        self.spec_file = None

        if not self.check_main_script():
            return
        if not self.check_nuitka():
            return
        if not self.check_nuitka_in_path():
            return

        # self.clean_previous_builds()
        self.generate_nuitka_command()
        self.insert_git_info()
        self.run_nuitka()

if __name__ == "__main__":
    app_builder = AppBuilder(app_name="TestApp", main_script=str(Path(__file__).parent.joinpath("test.py")))
    app_builder.dependency_dirs = [
        # (os.path.join(Path(__file__).parent.parent.parent, "mediso_packages"), "mediso_packages"),
        # (os.path.join(Path(__file__).parent, "web"), "web"),
        # (os.path.join(Path(__file__).parent, "blocks"), "blocks"),
        # (os.path.join(Path(__file__).parent, "layout.json"), ".")
    ]
    app_builder.build_installer()
