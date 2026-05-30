from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INTERFACE_DOCS_DIR = REPO_ROOT / "interface_docs"
if str(INTERFACE_DOCS_DIR) not in sys.path:
    sys.path.insert(0, str(INTERFACE_DOCS_DIR))


import generate  # noqa: E402
from generators.gen_mlxcheck import gen_mlx_report  # noqa: E402


def test_gen_mlx_report_reports_duplicates_and_free_ranges() -> None:
    data = {
        "interface": {
            "canopen": {
                "object dictionary": {
                    "status": {
                        "a": {"mlx": 0x310001},
                        "b": {"mlx": 0x310002},
                        "dup": {"mlx": 0x310002},
                    },
                    "config": {
                        "c": {"mlx": 0x310005},
                    },
                }
            }
        }
    }

    report = gen_mlx_report(data, min_mlx=0x310001, max_mlx=0x310006)

    assert "MLX in use: 4" in report
    assert "Duplicate MLX numbers: 0x310002" in report
    assert "- 0x310001 - 0x310002" in report
    assert "- 0x310005 - 0x310005" in report
    assert "Unused MLX numbers in range: 3" in report
    assert "Next available MLX: 0x310003" in report


def test_process_target_generates_mlx_report_file(tmp_path: Path) -> None:
    source_path = tmp_path / "demo.yaml"
    source_path.write_text(
        """
interface:
  transport: canopen
  canopen:
    object dictionary:
      status:
        value_a:
          mlx: 0x310001
        value_b:
          mlx: 0x310003
""".strip(),
        encoding="utf-8",
    )

    generate.process_target(
        {
            "source": "demo.yaml",
            "output": "reports/mlxcheck.txt",
            "format": "mlxcheck",
            "minMLX": 0x310001,
            "maxMLX": 0x310004,
        },
        tmp_path,
    )

    report_path = tmp_path / "reports" / "mlxcheck.txt"
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "MLX in use: 2" in report
    assert "Next available MLX: 0x310002" in report