"""MLX allocation report generator."""

from __future__ import annotations

from collections import Counter


def gen_mlx_report(data: dict, min_mlx: int | None = None, max_mlx: int | None = None) -> str:
    mlx_numbers = _extract_mlx_numbers(data)
    duplicates = sorted(mlx for mlx, count in Counter(mlx_numbers).items() if count > 1)
    lines = [f"MLX in use: {len(mlx_numbers)}"]

    if duplicates:
        lines.append("Duplicate MLX numbers: " + ", ".join(_format_hex(mlx) for mlx in duplicates))
    else:
        lines.append("Duplicate MLX numbers: none")

    used_intervals = _find_intervals(mlx_numbers)
    lines.append("MLX intervals in use:")
    if used_intervals:
        lines.extend(f"- {_format_hex(start)} - {_format_hex(end)}" for start, end in used_intervals)
    else:
        lines.append("- none")

    if min_mlx is not None and max_mlx is not None:
        unused_count, unused_intervals, next_free_mlx = _find_unused_intervals(mlx_numbers, min_mlx, max_mlx)
        lines.append(f"Unused MLX numbers in range: {unused_count}")
        lines.append("Unused MLX intervals:")
        if unused_intervals:
            lines.extend(f"- {_format_hex(start)} - {_format_hex(end)}" for start, end in unused_intervals)
        else:
            lines.append("- none")
        lines.append(
            "Next available MLX: " + (_format_hex(next_free_mlx) if next_free_mlx is not None else "none")
        )

    return "\n".join(lines) + "\n"


def _extract_mlx_numbers(data: dict) -> list[int]:
    object_dict = data.get("interface", {}).get("canopen", {}).get("object dictionary", {})
    mlx_numbers: list[int] = []
    for section in object_dict.values():
        for obj_data in section.values():
            mlx = obj_data.get("mlx")
            if isinstance(mlx, int):
                mlx_numbers.append(mlx)
    return sorted(mlx_numbers)


def _find_intervals(mlx_numbers: list[int]) -> list[tuple[int, int]]:
    if not mlx_numbers:
        return []

    intervals: list[tuple[int, int]] = []
    start = mlx_numbers[0]
    end = mlx_numbers[0]
    for mlx in mlx_numbers[1:]:
        if mlx == end + 1:
            end = mlx
            continue
        intervals.append((start, end))
        start = mlx
        end = mlx
    intervals.append((start, end))
    return intervals


def _find_unused_intervals(
    used_mlx_numbers: list[int],
    min_mlx: int,
    max_mlx: int,
) -> tuple[int, list[tuple[int, int]], int | None]:
    used_set = {mlx for mlx in used_mlx_numbers if min_mlx <= mlx <= max_mlx}
    unused_intervals: list[tuple[int, int]] = []
    next_free: int | None = None
    interval_start: int | None = None
    unused_count = 0

    for mlx in range(min_mlx, max_mlx + 1):
        if mlx in used_set:
            if interval_start is not None:
                unused_intervals.append((interval_start, mlx - 1))
                interval_start = None
            continue

        if next_free is None:
            next_free = mlx
        if interval_start is None:
            interval_start = mlx
        unused_count += 1

    if interval_start is not None:
        unused_intervals.append((interval_start, max_mlx))

    return unused_count, unused_intervals, next_free


def _format_hex(value: int) -> str:
    return f"0x{value:X}"