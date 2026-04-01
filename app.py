#!/usr/bin/env python3
"""
VRPCC — Approximation Algorithm (Yu, Nagarajan, Shen 2018).

Chạy Algorithm 2 (binary search trên B) + Algorithm 1 (MCG-VRP greedy)
với oracle k-TSP bicriteria (β = 5). Tuỳ chọn local search (2-opt + relocation).

In chi tiết: cận trên, cận dưới, B tốt nhất, makespan, chi phí từng xe, thời gian.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from vrpcc.approx_algorithm import VRPCCResult, algorithm_2_vrpcc
from vrpcc.approx_observer import NULL_OBSERVER
from vrpcc.approx_observer_logging import (
    LoggingApproxObserver,
    configure_approx_trace_file,
)
from vrpcc.instance import VRPCCInstance
from vrpcc.k_tsp_oracle import make_oracle
from vrpcc.local_search import local_search
from vrpcc.plotting import plot_approx_only_bars, plot_routes_map

SEP = "=" * 64


def _print_result(
    name: str,
    inst: VRPCCInstance,
    result: VRPCCResult,
    routes_final: list[list[int]],
    makespan_final: float,
    elapsed_total: float,
    use_ls: bool,
) -> None:
    n = inst.n_nodes
    log2n = math.ceil(math.log2(max(inst.n_customers, 2)))

    print(f"\n{SEP}")
    print(f"  Instance : {name}")
    print(f"  Nodes    : {n} (1 depot + {inst.n_customers} customers)")
    print(f"  Vehicles : {inst.m}")
    print(f"  Beta     : {result.beta}")
    print(f"  Epsilon  : {result.eps}")
    print(SEP)

    print(f"\n  Algorithm 2 — Binary Search trên B")
    print(f"  ─────────────────────────────────────")
    print(f"  Cận trên ban đầu u₀  = 2·Σc_ij = {result.B_init_upper:.4f}")
    print(f"  Cận dưới ban đầu l₀  = 0")
    print(f"  Số bước nhị phân     = {result.n_binary_steps}")
    print(f"  Số lượt greedy (B*)  = {result.n_waves_last_feasible}")
    print(f"  ───────────────────────────")
    print(f"  Cận dưới cuối  l     = {result.B_lower:.6f}")
    print(f"  Cận trên cuối  u     = {result.B_upper:.6f}")
    print(f"  B* oracle (= u)      = {result.B_upper:.6f}")
    print(f"  Ngưỡng oracle β·B*   = {result.beta * result.B_upper:.6f}")
    print(f"  Khoảng u - l         = {result.B_upper - result.B_lower:.6g}")
    print(
        "  Ghi chú: B* là ngân sách cho mỗi lời gọi O(Y,B,i) trong một wave; "
        "route cuối là nối nhiều wave nên có thể > β·B*."
    )

    print(f"\n  Cận xấp xỉ lý thuyết (Lemma 5)")
    print(f"  ─────────────────────────────────────")
    print(f"  ⌈log₂ n⌉            = {log2n}")
    print(f"  (1+ε)·β·⌈log₂ n⌉   = {result.approx_ratio_bound:.2f}")
    print(f"  → makespan ≤ {result.approx_ratio_bound:.2f} × OPT")

    print(f"\n  Tuyến xe (Algorithm 2)")
    print(f"  ─────────────────────────────────────")
    for k in range(inst.m):
        r = result.routes[k]
        custs = [v for v in r if v != 0]
        c = result.route_costs[k]
        print(f"  Xe {k}: {len(custs):2d} khách | cost = {c:10.4f} | {r}")

    print(f"\n  Makespan (Algorithm 2)     = {result.makespan:.4f}")

    if use_ls:
        print(f"\n  Local Search (2-opt + relocation)")
        print(f"  ─────────────────────────────────────")
        for k in range(inst.m):
            r = routes_final[k]
            custs = [v for v in r if v != 0]
            c = inst.tour_length(r, k) if len(r) >= 2 else 0.0
            print(f"  Xe {k}: {len(custs):2d} khách | cost = {c:10.4f} | {r}")
        print(f"\n  Makespan (sau local search) = {makespan_final:.4f}")

    print(f"\n  Thời gian")
    print(f"  ─────────────────────────────────────")
    print(f"  Algorithm 2          = {result.elapsed_sec:.3f}s")
    print(f"  Tổng (+ local search)= {elapsed_total:.3f}s")
    print(f"{SEP}\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="VRPCC: thuật toán bài báo (approx + local search), không MIP",
    )
    ap.add_argument(
        "--instance", type=Path, action="append",
        help="File JSON instance (lặp lại cho nhiều file)",
    )
    ap.add_argument(
        "--instance-dir", type=Path, action="append",
        help="Thư mục chứa các JSON instance (ví dụ: MIP/data, MIP/data2)",
    )
    ap.add_argument("--beta", type=float, default=5.0)
    ap.add_argument("--no-local-search", action="store_true")
    ap.add_argument("--eps", type=float, default=1e-3)
    ap.add_argument("--out-dir", type=Path, default=Path("output_runs"))
    ap.add_argument("--no-plots", action="store_true")
    ap.add_argument("--log-file", type=Path, default=None)
    ap.add_argument("--no-algorithm-log", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    algorithm_trace = (not args.no_algorithm_log) or args.verbose

    paths: list[Path] = []
    if args.instance:
        paths.extend(args.instance)
    if args.instance_dir:
        for d in args.instance_dir:
            dd = d if d.is_absolute() else (_ROOT / d)
            if dd.is_dir():
                paths.extend(sorted(dd.glob("*.json")))

    if not paths:
        inst_dir = _ROOT / "vrpcc" / "data" / "instances"
        paths = sorted(inst_dir.glob("*.json")) if inst_dir.is_dir() else []
    else:
        paths = sorted({p.resolve() for p in paths})

    if not paths:
        print("Không có instance. Chạy: python -m vrpcc.data.generate_instances")
        sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if algorithm_trace:
        log_path = args.log_file if args.log_file is not None else args.out_dir / "approx_algorithm.log"
        configure_approx_trace_file(log_path, mode="w")
        print(f"Trace → {log_path.resolve()}", flush=True)

    results_json: list[dict] = []
    use_ls = not args.no_local_search

    for p in paths:
        if p.name == "manifest.json":
            continue
        inst = VRPCCInstance.load_json(p)
        name = inst.name or p.stem

        oracle = make_oracle(inst, beta=args.beta)
        observer = LoggingApproxObserver() if algorithm_trace else NULL_OBSERVER
        observer.on_run_start(name)

        t_total_start = time.perf_counter()
        result = algorithm_2_vrpcc(
            inst, oracle, eps=args.eps, beta=args.beta, observer=observer,
        )

        if use_ls:
            routes_final = local_search(inst, result.routes)
            makespan_final = inst.makespan(routes_final)
        else:
            routes_final = result.routes
            makespan_final = result.makespan

        elapsed_total = time.perf_counter() - t_total_start

        _print_result(name, inst, result, routes_final, makespan_final, elapsed_total, use_ls)

        row = {
            "name": name,
            "file": str(p),
            "n_customers": inst.n_customers,
            "n_vehicles": inst.m,
            "beta": args.beta,
            "eps": args.eps,
            "B_lower": result.B_lower,
            "B_upper": result.B_upper,
            "B_init_upper": result.B_init_upper,
            "n_binary_steps": result.n_binary_steps,
            "approx_ratio_bound": result.approx_ratio_bound,
            "makespan_algo2": result.makespan,
            "makespan_final": makespan_final,
            "time_algo2": result.elapsed_sec,
            "time_total": elapsed_total,
            "local_search": use_ls,
        }
        results_json.append(row)

        if not args.no_plots and inst.coords is not None:
            plot_routes_map(
                inst, routes_final,
                args.out_dir / f"routes_paper_{name}.png",
                title=f"Thuật toán bài báo — {name}",
            )

    summary_path = args.out_dir / "summary_paper_only.json"
    summary_path.write_text(json.dumps(results_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Summary JSON → {summary_path}")

    if not args.no_plots and results_json:
        labels = [str(r["name"]) for r in results_json]
        plot_approx_only_bars(
            labels,
            [float(r["time_total"]) for r in results_json],
            [float(r["makespan_final"]) for r in results_json],
            args.out_dir / "approx_bars.png",
        )


if __name__ == "__main__":
    main()
