"""Run a power test profile.

Usage:
  run_profile.py run <profile_json> [--repo-root=<path>]

Options:
  --repo-root=<path>   Repo root folder [default: .]
"""

import pathlib
import sys

from docopt import docopt


def main() -> int:
    args = docopt(__doc__)
    repo_root = pathlib.Path(args["--repo-root"]).resolve()

    # Run from repo root without installing.
    sys.path.append(str(repo_root / "pyontrust_packages"))

    from power_test_framework.profiles import load_profile, run_profile  # noqa: E402

    profile_path = args["<profile_json>"]
    profile = load_profile(profile_path)
    out_dir = run_profile(profile, repo_root=repo_root)
    print(str(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
