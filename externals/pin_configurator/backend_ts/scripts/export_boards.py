from __future__ import annotations

import json
import pathlib
import sys


def main() -> int:
    backend_dir = pathlib.Path(__file__).resolve().parent.parent
    root_dir = backend_dir.parent

    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from board_schema import board_to_frontend
    from boards import BOARDS
    from clock_registry import get_all_clock_trees, get_clock_tree
    from module_registry import get_all_modules
    from peripheral_registry import get_all_peripheral_templates

    summaries: list[dict[str, object]] = []
    by_id: dict[str, dict[str, object]] = {}

    for board_id, builder in BOARDS.items():
        board = builder()
        summaries.append(
            {
                'id': board_id,
                'name': board.soc,
                'board': board.board,
                'package': board.package,
                'pin_count': board.pin_count,
            }
        )
        by_id[board_id] = board_to_frontend(board)

    snapshot = {
        'summaries': summaries,
        'byId': by_id,
    }

    module_snapshot = {
        'modules': get_all_modules(),
    }

    clock_summaries = get_all_clock_trees()
    clock_snapshot = {
        'summaries': clock_summaries,
        'byId': {
            summary['id']: get_clock_tree(summary['id'])
            for summary in clock_summaries
        },
    }

    peripheral_snapshot = {
        'templates': get_all_peripheral_templates(),
    }

    output_path = backend_dir / 'src' / 'generated' / 'boards.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
    (output_path.parent / 'modules.json').write_text(json.dumps(module_snapshot, indent=2), encoding='utf-8')
    (output_path.parent / 'clock_trees.json').write_text(json.dumps(clock_snapshot, indent=2), encoding='utf-8')
    (output_path.parent / 'peripheral_templates.json').write_text(json.dumps(peripheral_snapshot, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())