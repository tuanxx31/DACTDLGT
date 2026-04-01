"""
Generate raw VRPCC instances following Yu, Nagarajan, Shen (2018), Section 4:
- Coordinates: Solomon-style C (clustered), R (random), RC (mixed).
- Compatibility: Bernoulli(p) per (vehicle, customer); p=0.3 tight, p=0.7 relaxed.
- Repairs: each customer has >=1 vehicle; each vehicle can serve >=1 customer.
"""
from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, asdict
from typing import List, Tuple


@dataclass
class Instance:
    name: str
    n: int  # nodes including depot 0
    m: int  # vehicles
    prob_compat: float
    layout: str  # "C" | "R" | "RC"
    coords: List[List[float]]
    c: List[List[float]]  # distance matrix (symmetric, >= 1)
    u: List[List[float]]  # u[k][j] in {0.0, 1.0}; depot j=0 luon 1.0 (khong lam tron)


def _euclidean(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _dist_matrix(coords: List[Tuple[float, float]]) -> List[List[float]]:
    n = len(coords)
    c = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = _euclidean(coords[i], coords[j])
            # Paper: minimum distance at least 1; khong lam tron
            dij = max(1.0, d)
            c[i][j] = c[j][i] = dij
    return c


def _solomon_coords(
    rng: random.Random, n: int, layout: str
) -> List[Tuple[float, float]]:
    """n nodes: index 0 = depot, 1..n-1 customers. Layout C / R / RC."""
    # Scale similar to Solomon-style benchmarks (compact [0, 100] plane)
    W = 100.0

    def uniform() -> Tuple[float, float]:
        return (rng.uniform(0, W), rng.uniform(0, W))

    coords: List[Tuple[float, float]] = []
    depot = (0.5 * W, 0.5 * W)
    coords.append(depot)
    n_cust = n - 1

    if layout == "R":
        for _ in range(n_cust):
            coords.append(uniform())
    elif layout == "C":
        n_clusters = max(3, min(6, int(math.sqrt(n_cust))))
        centers = [(rng.uniform(0.15, 0.85) * W, rng.uniform(0.15, 0.85) * W) for _ in range(n_clusters)]
        rad = 0.08 * W
        for _ in range(n_cust):
            cx, cy = rng.choice(centers)
            coords.append(
                (
                    max(0.0, min(W, cx + rng.uniform(-rad, rad))),
                    max(0.0, min(W, cy + rng.uniform(-rad, rad))),
                )
            )
    elif layout == "RC":
        half = n_cust // 2
        n_clusters = max(3, min(5, int(math.sqrt(half))))
        centers = [(rng.uniform(0.15, 0.85) * W, rng.uniform(0.15, 0.85) * W) for _ in range(n_clusters)]
        rad = 0.08 * W
        for _ in range(half):
            cx, cy = rng.choice(centers)
            coords.append(
                (
                    max(0.0, min(W, cx + rng.uniform(-rad, rad))),
                    max(0.0, min(W, cy + rng.uniform(-rad, rad))),
                )
            )
        for _ in range(n_cust - half):
            coords.append(uniform())
    else:
        raise ValueError(f"Unknown layout {layout}")

    return coords


def _repair_compatibility(u: List[List[float]], m: int, n: int, rng: random.Random) -> None:
    """Ensure feasibility: each customer j>=1 has some vehicle; each vehicle serves some customer."""
    for j in range(1, n):
        if all(u[k][j] == 0.0 for k in range(m)):
            u[rng.randrange(m)][j] = 1.0
    for k in range(m):
        if all(u[k][j] == 0.0 for j in range(1, n)):
            u[k][rng.randrange(1, n)] = 1.0


def generate_instance(
    name: str,
    n: int,
    m: int,
    layout: str,
    prob_compat: float,
    seed: int,
) -> Instance:
    rng = random.Random(seed)
    raw = _solomon_coords(rng, n, layout)
    c = _dist_matrix(raw)
    u = [[0.0] * n for _ in range(m)]
    for k in range(m):
        u[k][0] = 1.0
    for k in range(m):
        for j in range(1, n):
            u[k][j] = 1.0 if rng.random() < prob_compat else 0.0
    _repair_compatibility(u, m, n, rng)
    return Instance(
        name=name,
        n=n,
        m=m,
        prob_compat=prob_compat,
        layout=layout,
        coords=[list(p) for p in raw],
        c=c,
        u=u,
    )


def instance_to_dict(inst: Instance) -> dict:
    d = asdict(inst)
    return d


def write_instance(inst: Instance, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(instance_to_dict(inst), f, indent=2)


def load_instance(path: str) -> Instance:
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return Instance(
        name=d["name"],
        n=d["n"],
        m=d["m"],
        prob_compat=d["prob_compat"],
        layout=d["layout"],
        coords=d["coords"],
        c=d["c"],
        u=d["u"],
    )


def build_all_default(root: str, prob_compat: float, seed_offset: int) -> None:
    """
    root: 'data' or 'data2'
    seed_offset: separates tight vs relaxed runs
    """
    n, m = 21, 6
    specs = [
        ("c-n21-k6", "C", 1000 + seed_offset),
        ("r-n21-k6", "R", 2000 + seed_offset),
        ("RC-n21-k6", "RC", 3000 + seed_offset),
    ]
    for folder, layout, seed in specs:
        name = folder
        inst = generate_instance(name, n, m, layout, prob_compat, seed)
        out = os.path.join(root, folder, f"{folder}.json")
        write_instance(inst, out)
if __name__ == "__main__":
    _base = os.path.dirname(os.path.abspath(__file__))
    build_all_default(os.path.join(_base, "data"), 0.3, 0)
    build_all_default(os.path.join(_base, "data2"), 0.7, 10000)
    print(f"Wrote {_base}/data and .../data2 (c, r, RC × n21-k6)")