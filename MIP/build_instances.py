"""
Sinh thô các instance C-n21-k6, R-n21-k6, RC-n21-k6 (21 nút = 1 kho + 20 khách, k=6 xe).
Ma trận tương thích u[k][i]: data = chặt, data2 = thoáng hơn.
Cùng tọa độ/khoảng cách giữa hai bộ; chỉ khác u.

Toa do lam tron truoc roi moi tinh c de khop voi JSON.
"""
from __future__ import annotations

import json
import math
import os
import random
from typing import List, Tuple

RNG_COORD = random.Random(20260401)
RNG_TIGHT = random.Random(3101)
RNG_RELAX = random.Random(4202)

N_NODES = 21
M_VEH = 6
CUSTOMERS = list(range(1, N_NODES))


def euclid_round(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    d = math.hypot(a[0] - b[0], a[1] - b[1])
    return round(d, 2)


def coords_clustered() -> List[Tuple[float, float]]:
    centers = [(20.0, 20.0), (80.0, 20.0), (50.0, 80.0)]
    pts = [(0.0, 0.0)]
    for i in range(20):
        cx, cy = centers[i % 3]
        pts.append((cx + RNG_COORD.gauss(0, 8), cy + RNG_COORD.gauss(0, 8)))
    return pts


def coords_random() -> List[Tuple[float, float]]:
    pts = [(0.0, 0.0)]
    for _ in range(20):
        pts.append((RNG_COORD.uniform(0, 100), RNG_COORD.uniform(0, 100)))
    return pts


def coords_rc() -> List[Tuple[float, float]]:
    c = coords_clustered()
    r = coords_random()
    pts = [(0.0, 0.0)]
    for i in range(1, N_NODES):
        pts.append(c[i] if i % 2 == 0 else r[i])
    return pts


def dist_matrix(coords: List[Tuple[float, float]]) -> List[List[float]]:
    n = len(coords)
    c = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                c[i][j] = euclid_round(coords[i], coords[j])
    return c


def ensure_coverage(
    u: List[List[int]], m: int, customers: List[int], rng: random.Random
) -> None:
    for j in customers:
        if sum(u[k][j] for k in range(m)) == 0:
            u[rng.randint(0, m - 1)][j] = 1


def build_u_tight(m: int, customers: List[int], rng: random.Random) -> List[List[int]]:
    n_nodes = N_NODES
    u = [[0] * n_nodes for _ in range(m)]
    for k in range(m):
        u[k][0] = 1
    p = 0.42
    for k in range(m):
        for j in customers:
            if rng.random() < p:
                u[k][j] = 1
    ensure_coverage(u, m, customers, rng)
    for j in customers:
        while sum(u[k][j] for k in range(m)) < 2:
            u[rng.randint(0, m - 1)][j] = 1
    return u


def build_u_relaxed(m: int, customers: List[int], rng: random.Random) -> List[List[int]]:
    n_nodes = N_NODES
    u = [[0] * n_nodes for _ in range(m)]
    for k in range(m):
        u[k][0] = 1
    p = 0.82
    for k in range(m):
        for j in customers:
            if rng.random() < p:
                u[k][j] = 1
    ensure_coverage(u, m, customers, rng)
    for j in customers:
        while sum(u[k][j] for k in range(m)) < 4:
            u[rng.randint(0, m - 1)][j] = 1
    return u


def instance_dict(name: str, coords: List[Tuple[float, float]], u: List[List[int]]) -> dict:
    rounded = [(round(x, 2), round(y, 2)) for x, y in coords]
    c = dist_matrix(rounded)
    return {
        "name": name,
        "n": N_NODES,
        "m": M_VEH,
        "depot": 0,
        "coordinates": [[x, y] for x, y in rounded],
        "c": c,
        "u": u,
    }


def write_all(base: str) -> None:
    os.makedirs(os.path.join(base, "data"), exist_ok=True)
    os.makedirs(os.path.join(base, "data2"), exist_ok=True)

    specs = [
        ("C-n21-k6", coords_clustered),
        ("R-n21-k6", coords_random),
        ("RC-n21-k6", coords_rc),
    ]

    for name, fn in specs:
        coords = fn()
        ut = build_u_tight(M_VEH, CUSTOMERS, RNG_TIGHT)
        ur = build_u_relaxed(M_VEH, CUSTOMERS, RNG_RELAX)
        for folder, uu in (("data", ut), ("data2", ur)):
            path = os.path.join(base, folder, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(instance_dict(name, coords, uu), f, indent=2)
            print("Wrote", path)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    write_all(here)
