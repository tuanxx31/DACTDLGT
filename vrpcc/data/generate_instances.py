"""Generate VRPCC instances: Solomon coords + random compatibility (paper: 30% / 70%)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from vrpcc.data.solomon_loader import euclidean_dist_matrix, sample_instance_coords
from vrpcc.instance import VRPCCInstance


def _ensure_coverage(u: np.ndarray, n_nodes: int, m: int, rng: np.random.Generator) -> np.ndarray:
    """Every customer j>=1 must have sum_k u[k,j] >= 1."""
    u = u.copy()
    for j in range(1, n_nodes):
        if u[:, j].sum() == 0:
            k = int(rng.integers(0, m))
            u[k, j] = 1
    return u


def random_compatibility(m: int, n_nodes: int, p: float, rng: np.random.Generator) -> np.ndarray:
    u = rng.random((m, n_nodes)) < p
    u = u.astype(np.int8)
    u[:, 0] = 1  # depot
    return _ensure_coverage(u, n_nodes, m, rng)


def synthetic_coords(kind: str, n_customers: int, seed: int) -> np.ndarray:
    """R / C / RC style 2D points (depot at center-ish)."""
    rng = np.random.default_rng(seed)
    n = n_customers + 1
    depot = np.array([[50.0, 50.0]])
    cust = np.zeros((n_customers, 2))
    if kind == "R":
        cust = rng.uniform(0, 100, size=(n_customers, 2))
    elif kind == "C":
        n_centers = max(3, n_customers // 7 + 1)
        centers = rng.uniform(15, 85, size=(n_centers, 2))
        assign = rng.integers(0, n_centers, size=n_customers)
        noise = rng.normal(0, 4.0, size=(n_customers, 2))
        cust = centers[assign] + noise
        cust = np.clip(cust, 0, 100)
    elif kind == "RC":
        half = n_customers // 2
        r_part = rng.uniform(0, 100, size=(half, 2))
        n_centers = max(2, (n_customers - half) // 5 + 1)
        centers = rng.uniform(15, 85, size=(n_centers, 2))
        assign = rng.integers(0, n_centers, size=n_customers - half)
        noise = rng.normal(0, 3.5, size=(n_customers - half, 2))
        c_part = centers[assign] + noise
        c_part = np.clip(c_part, 0, 100)
        cust[:half] = r_part
        cust[half:] = c_part
    else:
        raise ValueError("kind must be R, C, or RC")
    return np.vstack([depot, cust])


def build_instance(
    *,
    kind: str,
    n_customers: int,
    m_vehicles: int,
    tight: bool,
    seed: int,
    solomon_path: str | Path | None = None,
    name: str = "",
) -> VRPCCInstance:
    p = 0.3 if tight else 0.7
    rng = np.random.default_rng(seed)
    if solomon_path is not None:
        coords = sample_instance_coords(solomon_path, n_customers, seed=0, start_index=0)
        # optional light shuffle of customers only (keep depot row 0)
        perm = np.arange(coords.shape[0])
        cperm = rng.permutation(n_customers) + 1
        perm[1:] = cperm
        coords = coords[perm]
    else:
        coords = synthetic_coords(kind, n_customers, seed)
    dist = euclidean_dist_matrix(coords)
    u = random_compatibility(m_vehicles, coords.shape[0], p, rng)
    meta = {
        "kind": kind,
        "n_customers": n_customers,
        "m_vehicles": m_vehicles,
        "tight": tight,
        "compat_prob": p,
        "seed": seed,
        "solomon": str(solomon_path) if solomon_path else None,
    }
    nm = name or f"{kind}-n{n_customers}-k{m_vehicles}-{'tight' if tight else 'relaxed'}-s{seed}"
    return VRPCCInstance(dist=dist, u=u, name=nm, metadata=meta, coords=coords)


# Mặc định: ít instance, n nhỏ — cùng run_comparison (MIP ~40s/instance, 1 lần) gói ~≤2 phút.
QUICK_SPECS: list[tuple[str, int, int, bool, int]] = [
    ("R", 6, 2, True, 1),
    ("R", 6, 2, False, 2),
    ("C", 8, 3, True, 3),
]

# Bộ lớn gần bài báo (chạy lâu).
FULL_SPECS: list[tuple[str, int, int, bool, int]] = [
    ("R", 10, 3, True, 1),
    ("R", 10, 3, False, 2),
    ("C", 14, 4, True, 3),
    ("C", 14, 4, False, 4),
    ("RC", 20, 5, True, 5),
    ("RC", 20, 5, False, 6),
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate VRPCC JSON instances")
    ap.add_argument("--out-dir", type=Path, default=Path("vrpcc/data/instances"))
    ap.add_argument("--solomon", type=Path, default=None, help="Optional Solomon .txt path")
    ap.add_argument(
        "--full",
        action="store_true",
        help="Sinh bộ lớn (giống thử nghiệm bài báo, chậm). Mặc định: bộ nhỏ cho chạy nhanh.",
    )
    ap.add_argument(
        "--clean",
        action="store_true",
        help="Xóa mọi file *.json trong out-dir trước khi ghi (tránh giữ instance cũ to hơn).",
    )
    args = ap.parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.clean:
        for f in out_dir.glob("*.json"):
            f.unlink()

    specs = FULL_SPECS if args.full else QUICK_SPECS
    manifest: list[dict] = []
    for kind, n, m, tight, seed in specs:
        inst = build_instance(
            kind=kind,
            n_customers=n,
            m_vehicles=m,
            tight=tight,
            seed=seed,
            solomon_path=args.solomon,
        )
        path = out_dir / f"{inst.name}.json"
        inst.save_json(path)
        print("Wrote", path)
        manifest.append(
            {
                "file": path.name,
                "kind": kind,
                "n": n,
                "m": m,
                "tight": tight,
                "seed": seed,
            }
        )

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
