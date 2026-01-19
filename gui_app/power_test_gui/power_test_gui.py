import pathlib
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Power Test Runner")
        self.geometry("720x420")

        self.profile_path = tk.StringVar(value=str(REPO_ROOT / "scripts" / "power_tests" / "example_profile.json"))
        self.output = tk.Text(self, height=18)

        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=10)

        tk.Label(frm, text="Profile JSON:").pack(side="left")
        tk.Entry(frm, textvariable=self.profile_path, width=70).pack(side="left", padx=8)
        tk.Button(frm, text="Browse", command=self.browse).pack(side="left")

        btns = tk.Frame(self)
        btns.pack(fill="x", padx=10)
        tk.Button(btns, text="Run", command=self.run_profile).pack(side="left")
        tk.Button(btns, text="Clear", command=lambda: self.output.delete("1.0", "end")).pack(side="left", padx=8)

        self.output.pack(fill="both", expand=True, padx=10, pady=10)

    def browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select profile JSON",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            initialdir=str(REPO_ROOT),
        )
        if path:
            self.profile_path.set(path)

    def log(self, line: str) -> None:
        self.output.insert("end", line + "\n")
        self.output.see("end")

    def run_profile(self) -> None:
        profile = self.profile_path.get().strip()
        if not profile:
            messagebox.showerror("Error", "Profile path is empty")
            return

        def _worker() -> None:
            try:
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "power_tests" / "run_profile.py"),
                    "run",
                    profile,
                    f"--repo-root={REPO_ROOT}",
                ]
                self.log("Running: " + " ".join(cmd))
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.stdout:
                    self.log(proc.stdout.strip())
                if proc.stderr:
                    self.log(proc.stderr.strip())
                if proc.returncode != 0:
                    self.log(f"FAILED rc={proc.returncode}")
                else:
                    self.log("OK")
            except Exception as exc:  # noqa: BLE001
                self.log(repr(exc))

        threading.Thread(target=_worker, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
