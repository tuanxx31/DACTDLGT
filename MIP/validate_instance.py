"""
Kiểm tra instance JSON: kích thước, đối xứng c, phủ u, khớp c với coordinates.
Chạy: python validate_instance.py
      python validate_instance.py data/C-n21-k6.json
"""
from __future__ import annotations

import json
import math
import os
import sys


def check(path: str) -> bool:
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    n, m = d["n"], d["m"]
    c, u = d["c"], d["u"]
    coords = d["coordinates"]
    name = d.get("name", path)

    err: list[str] = []

    if len(c) != n or any(len(row) != n for row in c):
        err.append(f"c phai la {n}x{n}")
    if len(u) != m or any(len(row) != n for row in u):
        err.append(f"u phai la {m}x{n}")
    if len(coords) != n:
        err.append(f"coordinates phai co {n} diem")

    if not err:
        mx = max(abs(c[i][j] - c[j][i]) for i in range(n) for j in range(n))
        if mx > 1e-9:
            err.append(f"c khong doi xung: max diff {mx}")

    if not err:
        for i in range(n):
            for j in range(n):
                if i == j:
                    if c[i][j] != 0:
                        err.append(f"c[{i}][{j}] phai 0")
                else:
                    dx = coords[i][0] - coords[j][0]
                    dy = coords[i][1] - coords[j][1]
                    eucl = round(math.hypot(dx, dy), 2)
                    if abs(c[i][j] - eucl) > 1e-6:
                        err.append(f"c[{i}][{j}]={c[i][j]} khac sqrt tu toa do {eucl}")
                        break
            if err:
                break

    if not err:
        for k in range(m):
            if u[k][0] != 1:
                err.append(f"u[{k}][0] (kho) phai 1")
                break
        for j in range(1, n):
            if sum(u[k][j] for k in range(m)) < 1:
                err.append(f"khach {j} khong co xe nao phuc vu")
                break

    if err:
        print(f"[FAIL] {name}: {err[0]}")
        for e in err[1:]:
            print(f"       {e}")
        return False

    print(f"[OK] {name}: c doi xung, khop coordinates, u phu khach.")
    return True


def main() -> None:
    base = os.path.dirname(os.path.abspath(__file__))
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
    else:
        paths = []
        for folder in ("data", "data2"):
            for fn in ("C-n21-k6.json", "R-n21-k6.json", "RC-n21-k6.json"):
                paths.append(os.path.join(base, folder, fn))
    ok = all(check(p) for p in paths)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
