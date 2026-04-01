"""
Chạy MIP trên ví dụ nhỏ (data_small):
  Kho 0, khách {1,2,3,4}, xe (0,1)
  V0 = {1,2,3}, V1 = {2,3,4}
  Ma trận c được khai báo thủ công trong example-n5-k2.json
"""
from __future__ import annotations

import os
import sys

from instancegen import load_instance
from vrpcc_mip import format_mip_summary, solve_vrpcc

HERE = os.path.dirname(os.path.abspath(__file__))
INSTANCE_PATH = os.path.join(HERE, "data_small", "example-n5-k2.json")


def main() -> None:
    tl = float(os.environ.get("VRPCC_TIME_LIMIT", "600"))
    verbose = os.environ.get("VRPCC_VERBOSE", "0") == "1"

    if not os.path.isfile(INSTANCE_PATH):
        print(f"Missing: {INSTANCE_PATH}", file=sys.stderr)
        sys.exit(1)

    inst = load_instance(INSTANCE_PATH)

    print("=== Small example: n=5 (depot + 4 customers), m=2 vehicles ===")
    print("V0 = {1,2,3}, V1 = {2,3,4} (see u in JSON)")
    print("MIP (min tau):")

    rep = solve_vrpcc(inst, time_limit=tl, verbose=verbose)
    print(format_mip_summary(rep))


if __name__ == "__main__":
    main()