"""Chạy MIP VRPCC trên bộ dữ liệu tương thích chặt (`data/`).

Traceback tại subprocess.wait / cbc.wait thường là bạn đã nhấn Ctrl+C
để ngắt khi CBC đang chạy lâu — không phải lỗi cài đặt.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vrpcc_mip as vm


def main() -> None:
    # Mặc định ~2 phút/instance (CBC); tăng time_budget_sec nếu cần LB chặt hơn
    results = vm.solve_folder(
        "data",
        time_budget_sec=120,
        per_solve_cap_sec=60,
        max_iters=25,
    )
    for r in results:
        print(
            f"{r.name}: status={r.status}, stop={r.stop_reason!r}, tau={r.tau}, "
            f"time={r.time_sec:.2f}s — {r.message}"
        )


if __name__ == "__main__":
    main()
