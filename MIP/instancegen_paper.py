"""
Generate paper-style VRPCC instances from Solomon benchmark text files.

Reference (Section 4, computational setup):
  "An Approximation Algorithm for Vehicle Routing with Compatibility Constraints"
  Yu, Nagarajan, Shen (2018)

Paper-aligned rules used here:
  - Use node locations from Solomon benchmark files (R / C / RC).
  - Build Euclidean distance matrix, symmetric, with minimum distance at least 1.
  - Generate compatibility u[k][j] by Bernoulli(p):
      * p = 0.3 for tight set
      * p = 0.7 for relaxed set
  - Keep depot compatibility u[k][0] = 1 for all vehicles.
  - Ensure feasibility: each customer j >= 1 has at least one compatible vehicle.

This script creates two suites:
  1) up-to-101 suite (instances in Tables 3/4 of Optimization-Online preprint)
  2) up-to-26 suite (instances in Tables 1/2 of Optimization-Online preprint)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class Instance:
    name: str
    n: int  # number of nodes including depot
    m: int  # number of vehicles
    prob_compat: float
    layout: str  # C | R | RC
    coords: list[list[float]]
    c: list[list[float]]
    u: list[list[float]]


@dataclass
class Spec:
    n_nodes: int
    m_vehicles: int


ROW_RE = re.compile(
    r"^\s*(\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*$"
)


def _load_solomon_coords(path: Path) -> list[tuple[int, float, float]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rows: list[tuple[int, float, float]] = []
    for line in lines:
        m = ROW_RE.match(line)
        if not m:
            continue
        nid = int(m.group(1))
        x = float(m.group(2))
        y = float(m.group(3))
        rows.append((nid, x, y))
    if not rows:
        raise ValueError(f"Cannot parse Solomon rows from: {path}")
    return rows


def _take_prefix_nodes(rows: list[tuple[int, float, float]], n_nodes: int) -> list[tuple[float, float]]:
    max_id = n_nodes - 1
    picked = [(x, y) for nid, x, y in rows if nid <= max_id]
    if len(picked) != n_nodes:
        raise ValueError(
            f"Need {n_nodes} rows (id 0..{max_id}), got {len(picked)} rows"
        )
    return picked


def _dist_matrix(coords: list[tuple[float, float]]) -> list[list[float]]:
    n = len(coords)
    c = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = coords[i]
        for j in range(i + 1, n):
            xj, yj = coords[j]
            d = math.hypot(xi - xj, yi - yj)
            dij = max(1.0, d)
            c[i][j] = dij
            c[j][i] = dij
    return c


def _compatibility(m: int, n: int, p: float, rng: random.Random) -> list[list[float]]:
    u = [[0.0] * n for _ in range(m)]
    for k in range(m):
        u[k][0] = 1.0
    for j in range(1, n):
        compatible = []
        for k in range(m):
            if rng.random() < p:
                u[k][j] = 1.0
                compatible.append(k)
        if not compatible:
            u[rng.randrange(m)][j] = 1.0
    return u


def _instance_name(layout: str, n_nodes: int, m_vehicles: int) -> str:
    if layout == "C":
        prefix = "c"
    elif layout == "R":
        prefix = "r"
    elif layout == "RC":
        prefix = "RC"
    else:
        raise ValueError(f"Unknown layout: {layout}")
    return f"{prefix}-n{n_nodes}-k{m_vehicles}"


def _seed(layout: str, spec_idx: int, suite_offset: int, relaxed: bool) -> int:
    base = {"C": 1000, "R": 2000, "RC": 3000}[layout]
    level_offset = 10000 if relaxed else 0
    return base + suite_offset + level_offset + 100 * spec_idx


def _suite_specs(kind: str) -> list[Spec]:
    if kind == "up_to_101":
        return [
            Spec(21, 6),
            Spec(41, 10),
            Spec(61, 14),
            Spec(81, 18),
            Spec(101, 22),
        ]
    if kind == "up_to_26":
        return [
            Spec(11, 4),
            Spec(16, 4),
            Spec(21, 6),
            Spec(26, 6),
        ]
    raise ValueError(f"Unknown suite kind: {kind}")


def _source_subset_for_n(n_nodes: int) -> str:
    # User-requested mapping:
    # n21 from 25-customer set
    # n41 from 50-customer set
    # n61, n81, n101 from 100-customer set
    # (Small suite n11/n16/n26 naturally also comes from 25-customer set.)
    if n_nodes <= 26:
        return "25"
    if n_nodes == 41:
        return "50"
    if n_nodes in (61, 81, 101):
        return "100/txt"
    raise ValueError(f"No source subset rule for n={n_nodes}")


def _source_file_for_layout(layout: str) -> str:
    # Canonical representative in each Solomon category.
    return {
        "C": "c101.txt",
        "R": "r101.txt",
        "RC": "rc101.txt",
    }[layout]


def _write_instance(inst: Instance, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(asdict(inst), f, indent=2)


def _build_one(
    *,
    layout: str,
    spec: Spec,
    p: float,
    seed: int,
    solomon_path: Path,
) -> Instance:
    rows = _load_solomon_coords(solomon_path)
    coords_xy = _take_prefix_nodes(rows, spec.n_nodes)
    c = _dist_matrix(coords_xy)
    rng = random.Random(seed)
    u = _compatibility(spec.m_vehicles, spec.n_nodes, p, rng)
    name = _instance_name(layout, spec.n_nodes, spec.m_vehicles)
    return Instance(
        name=name,
        n=spec.n_nodes,
        m=spec.m_vehicles,
        prob_compat=p,
        layout=layout,
        coords=[[x, y] for (x, y) in coords_xy],
        c=c,
        u=u,
    )


def _generate_suite(
    *,
    out_root: Path,
    solomon_root: Path,
    suite_name: str,
    suite_specs: list[Spec],
    include_tight: bool,
    include_relaxed: bool,
    suite_offset: int,
) -> None:
    manifest_json: list[dict] = []
    manifest_csv_rows: list[dict[str, str]] = []

    for relaxed in (False, True):
        if relaxed and not include_relaxed:
            continue
        if (not relaxed) and not include_tight:
            continue
        level_dir = "relaxed" if relaxed else "tight"
        p = 0.7 if relaxed else 0.3

        for spec_idx, spec in enumerate(suite_specs):
            src_subset = _source_subset_for_n(spec.n_nodes)
            for layout in ("C", "R", "RC"):
                src_file = _source_file_for_layout(layout)
                src_path = solomon_root / src_subset / src_file
                if not src_path.is_file():
                    raise FileNotFoundError(f"Missing source file: {src_path}")

                sd = _seed(layout, spec_idx=spec_idx, suite_offset=suite_offset, relaxed=relaxed)
                inst = _build_one(
                    layout=layout,
                    spec=spec,
                    p=p,
                    seed=sd,
                    solomon_path=src_path,
                )

                out_dir = out_root / level_dir / inst.name
                out_path = out_dir / f"{inst.name}.json"
                _write_instance(inst, out_path)

                rec = {
                    "suite": suite_name,
                    "level": level_dir,
                    "instance_name": inst.name,
                    "n_nodes": inst.n,
                    "m_vehicles": inst.m,
                    "layout": inst.layout,
                    "compat_prob": inst.prob_compat,
                    "seed": sd,
                    "source_subset": src_subset,
                    "source_file": src_file,
                    "source_path": str(src_path).replace("\\", "/"),
                    "output_path": str(out_path).replace("\\", "/"),
                }
                manifest_json.append(rec)
                manifest_csv_rows.append({k: str(v) for k, v in rec.items()})

    with (out_root / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest_json, f, indent=2)
    with (out_root / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        if manifest_csv_rows:
            headers = list(manifest_csv_rows[0].keys())
            w = csv.DictWriter(f, fieldnames=headers)
            w.writeheader()
            w.writerows(manifest_csv_rows)


def _count_jsons(root: Path) -> int:
    return sum(1 for p in root.rglob("*.json") if p.name != "manifest.json")


def _check_instance_files(files: Iterable[Path]) -> None:
    for p in files:
        d = json.loads(p.read_text(encoding="utf-8"))
        n = int(d["n"])
        m = int(d["m"])
        c = d["c"]
        u = d["u"]

        if len(c) != n or any(len(row) != n for row in c):
            raise ValueError(f"Bad distance shape: {p}")
        if len(u) != m or any(len(row) != n for row in u):
            raise ValueError(f"Bad compatibility shape: {p}")

        # Symmetry + non-negative check.
        for i in range(n):
            if abs(float(c[i][i])) > 1e-9:
                raise ValueError(f"Distance diagonal must be zero: {p}")
            for j in range(i + 1, n):
                if abs(float(c[i][j]) - float(c[j][i])) > 1e-9:
                    raise ValueError(f"Distance matrix not symmetric: {p}")
                if float(c[i][j]) < 1.0:
                    raise ValueError(f"Distance must be >= 1 for i!=j: {p}")

        # Depot compatibility
        for k in range(m):
            if float(u[k][0]) != 1.0:
                raise ValueError(f"Depot compatibility must be 1: {p}")

        # Feasibility: each customer has at least one compatible vehicle.
        for j in range(1, n):
            if not any(float(u[k][j]) >= 0.5 for k in range(m)):
                raise ValueError(f"Infeasible customer compatibility at node {j}: {p}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate paper-style VRPCC instances from Solomon data")
    ap.add_argument(
        "--solomon-root",
        type=Path,
        default=Path("raw_data/solomon"),
        help="Root folder containing Solomon subsets (25, 50, 100/txt)",
    )
    ap.add_argument(
        "--out-root-101",
        type=Path,
        default=Path("MIP/data_paper_101"),
        help="Output root for suite up to 101 nodes",
    )
    ap.add_argument(
        "--out-root-26",
        type=Path,
        default=Path("MIP/data_paper_26"),
        help="Output root for suite up to 26 nodes",
    )
    ap.add_argument("--skip-101", action="store_true", help="Skip generating up-to-101 suite")
    ap.add_argument("--skip-26", action="store_true", help="Skip generating up-to-26 suite")
    ap.add_argument("--tight-only", action="store_true", help="Generate only tight (p=0.3)")
    ap.add_argument("--relaxed-only", action="store_true", help="Generate only relaxed (p=0.7)")
    ap.add_argument("--clean", action="store_true", help="Delete output suite folders before regenerating")
    args = ap.parse_args()

    if args.tight_only and args.relaxed_only:
        raise ValueError("Cannot combine --tight-only and --relaxed-only")

    include_tight = not args.relaxed_only
    include_relaxed = not args.tight_only

    solomon_root = args.solomon_root
    if not solomon_root.is_dir():
        raise FileNotFoundError(f"Solomon root not found: {solomon_root}")

    targets: list[tuple[Path, str, list[Spec], int]] = []
    if not args.skip_101:
        targets.append((args.out_root_101, "up_to_101", _suite_specs("up_to_101"), 0))
    if not args.skip_26:
        # Offset seeds so n21 in this suite is independent from n21 in up_to_101 suite.
        targets.append((args.out_root_26, "up_to_26", _suite_specs("up_to_26"), 50000))

    if not targets:
        print("No suite selected. Nothing to do.")
        return

    for out_root, suite_name, specs, seed_offset in targets:
        if args.clean and out_root.exists():
            # Manual recursive delete to avoid shelling out.
            for p in sorted(out_root.rglob("*"), key=lambda x: len(x.parts), reverse=True):
                if p.is_file():
                    p.unlink()
                elif p.is_dir():
                    p.rmdir()
            if out_root.exists():
                out_root.rmdir()

        out_root.mkdir(parents=True, exist_ok=True)
        _generate_suite(
            out_root=out_root,
            solomon_root=solomon_root,
            suite_name=suite_name,
            suite_specs=specs,
            include_tight=include_tight,
            include_relaxed=include_relaxed,
            suite_offset=seed_offset,
        )
        files = [p for p in out_root.rglob("*.json") if p.name != "manifest.json"]
        _check_instance_files(files)
        print(f"[OK] {suite_name}: wrote {_count_jsons(out_root)} instance files at {out_root}")


if __name__ == "__main__":
    main()
