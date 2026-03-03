#!/usr/bin/env python3
"""
Chạy trực tiếp thuật toán trong vrpcc_core.py (không cần UI web).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from vrpcc_core import (
    build_demo_instance,
    format_solution,
    instance_from_json_str,
    solve_vrpcc_approx,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chạy Algorithm 1 + 2 cho VRPCC từ CLI.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Đường dẫn file JSON kỹ thuật (dist/points + compatible).",
    )
    parser.add_argument("--eps", type=float, default=1e-2, help="Ngưỡng dừng cho binary-search.")
    parser.add_argument("--beta", type=float, default=1.0, help="Hệ số bicriteria beta (>=1).")
    parser.add_argument(
        "--no-local-search",
        action="store_true",
        help="Tắt hậu xử lý 2-opt + relocation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.input is None:
        instance = build_demo_instance()
    else:
        raw = args.input.read_text(encoding="utf-8")
        instance = instance_from_json_str(raw)

    solution = solve_vrpcc_approx(
        instance,
        eps=args.eps,
        beta=args.beta,
        apply_local_search=not args.no_local_search,
    )
    print(format_solution(solution, instance))


if __name__ == "__main__":
    main()
