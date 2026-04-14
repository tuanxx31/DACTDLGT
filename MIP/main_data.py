"""
Chạy MIP trên bộ dữ liệu `data`: tương thích chặt (p = 0.3 theo bài báo).
"""
from __future__ import annotations

import os
import sys

from instancegen import load_instance
from vrpcc_mip import format_mip_summary, solve_vrpcc

# DATA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_paper_101/tight")
DATA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

INSTANCES = ("c-n21-k6", "r-n21-k6")



def main() -> None:
    tl = float(os.environ.get("VRPCC_TIME_LIMIT", "600"))
    verbose = os.environ.get("VRPCC_VERBOSE", "0") == "1"
    for name in INSTANCES:
        path = os.path.join(DATA_ROOT, name, f"{name}.json")
        if not os.path.isfile(path):
            print(f"Thiếu file: {path}", file=sys.stderr)
            sys.exit(1)
        inst = load_instance(path)
        print(f"\n=== {name} | tight compatibility prob={inst.prob_compat} | layout={inst.layout} ===")
        print("MIP (min tau) - Gurobi report:")
        rep = solve_vrpcc(inst, time_limit=tl, verbose=verbose)
        print(format_mip_summary(rep))


if __name__ == "__main__":
    main()
