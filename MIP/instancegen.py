"""
Generate raw VRPCC instances following Yu, Nagarajan, Shen (2018), Section 4:
- Coordinates: Solomon-style C (clustered), R (random), RC (mixed).
- Compatibility: Bernoulli(p) per (vehicle, customer); p=0.3 tight, p=0.7 relaxed.
- Repairs: each customer has >=1 vehicle; each vehicle can serve >=1 customer.
"""
from __future__ import annotations

import argparse
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


def build_family(
    root: str,
    *,
    n_customers: int,
    n_vehicles: int,
    prob_compat: float,
    seed_offset: int,
) -> None:
    """
    Sinh 3 layout C/R/RC cho một cặp (n_customers, n_vehicles).
    Tên theo paper style: c-nXX-kYY, r-nXX-kYY, RC-nXX-kYY.
    """
    n = n_customers + 1  # + depot
    specs = [
        (f"c-n{n_customers}-k{n_vehicles}", "C", 1000 + seed_offset),
        (f"r-n{n_customers}-k{n_vehicles}", "R", 2000 + seed_offset),
        (f"RC-n{n_customers}-k{n_vehicles}", "RC", 3000 + seed_offset),
    ]
    for folder, layout, seed in specs:
        inst = generate_instance(folder, n, n_vehicles, layout, prob_compat, seed)
        out = os.path.join(root, folder, f"{folder}.json")
        write_instance(inst, out)


def _parse_size_token(token: str) -> tuple[int, int]:
    """
    Parse "41:10" -> (41 customers, 10 vehicles).
    """
    parts = token.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid size token '{token}', expected n_customers:n_vehicles")
    n_customers = int(parts[0].strip())
    n_vehicles = int(parts[1].strip())
    if n_customers <= 0 or n_vehicles <= 0:
        raise ValueError(f"Invalid positive values in token '{token}'")
    return n_customers, n_vehicles


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate VRPCC MIP instances (paper-style names, C/R/RC)."
    )
    ap.add_argument(
        "--size",
        action="append",
        default=[],
        help="Instance size as n_customers:n_vehicles (repeatable), e.g. 21:6 --size 41:10",
    )
    ap.add_argument(
        "--roots",
        nargs="+",
        default=["data", "data2"],
        help="Output folders under MIP/, default: data data2",
    )
    ap.add_argument(
        "--tight-p",
        type=float,
        default=0.3,
        help="Compatibility probability for tight set (default 0.3)",
    )
    ap.add_argument(
        "--relaxed-p",
        type=float,
        default=0.7,
        help="Compatibility probability for relaxed set (default 0.7)",
    )
    args = ap.parse_args()

    sizes: list[tuple[int, int]]
    if args.size:
        sizes = [_parse_size_token(tok) for tok in args.size]
    else:
        sizes = [(21, 6)]

    base = os.path.dirname(os.path.abspath(__file__))
    for root_name in args.roots:
        out_root = os.path.join(base, root_name)
        os.makedirs(out_root, exist_ok=True)
        is_relaxed = root_name.lower().endswith("2")
        p = args.relaxed_p if is_relaxed else args.tight_p
        seed_offset_base = 10000 if is_relaxed else 0
        for idx, (n_customers, n_vehicles) in enumerate(sizes):
            build_family(
                out_root,
                n_customers=n_customers,
                n_vehicles=n_vehicles,
                prob_compat=p,
                seed_offset=seed_offset_base + 100 * idx,
            )
    size_text = ", ".join([f"n{n}-k{m}" for n, m in sizes])
    print(f"Wrote {size_text} to roots: {', '.join(args.roots)}")


if __name__ == "__main__":
    main()