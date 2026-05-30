from __future__ import annotations

import argparse

from app_factory import create_app


__version__ = "0.1.0"


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo Dashboard generated dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5410)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()