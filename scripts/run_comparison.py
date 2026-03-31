#!/usr/bin/env python3
"""
VRPCC: thuật toán bài báo (mục 3–4) + tuỳ chọn MIP so sánh.

Mặc định gói nhanh (~≤2 phút với instance nhỏ trong vrpcc/data/instances): MIP 40s/instance, không chạy MIP lần 2.
--skip-mip: chỉ approx (+ local search), không Gurobi (vài giây).
--mip-limit-1 / --mip-limit-2: tăng khi cần thử nghiệm giống bài báo.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# repo root on path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from vrpcc.approx_algorithm import algorithm_2_vrpcc
from vrpcc.approx_observer import NULL_OBSERVER
from vrpcc.approx_observer_logging import (
    LoggingApproxObserver,
    configure_approx_trace_file,
)
from vrpcc.instance import VRPCCInstance
from vrpcc.k_tsp_oracle import make_oracle
from vrpcc.local_search import local_search
from vrpcc.plotting import plot_from_results_list, plot_routes_map


def _run_approx(
    inst: VRPCCInstance,
    beta: float,
    use_ls: bool,
    *,
    algorithm_trace: bool = True,
) -> tuple[list[list[int]], float, float, float]:
    oracle = make_oracle(inst, beta=beta)
    observer = LoggingApproxObserver() if algorithm_trace else NULL_OBSERVER
    t0 = time.perf_counter()
    observer.on_run_start(inst.name or "instance")
    routes, B = algorithm_2_vrpcc(inst, oracle, eps=1e-3, observer=observer)
    if use_ls:
        routes = local_search(inst, routes)
    elapsed = time.perf_counter() - t0
    obj = inst.makespan(routes)
    return routes, elapsed, obj, B


def main() -> None:
    ap = argparse.ArgumentParser(
        description="VRPCC: thuật toán bài báo (chính) vs MIP (so sánh)",
    )
    ap.add_argument(
        "--instance",
        type=Path,
        action="append",
        help="JSON instance (lặp lại cho nhiều file). Mặc định: tất cả *.json trong vrpcc/data/instances",
    )
    ap.add_argument(
        "--mip-limit-1",
        type=float,
        default=40.0,
        help="Time limit MIP lần 1 (giây); mặc định 40 để cả batch ~≤2 phút với instance nhỏ",
    )
    ap.add_argument(
        "--mip-limit-2",
        type=float,
        default=0.0,
        help="Time limit MIP lần 2 (giây); mặc định 0=bỏ qua. Đặt >0 và khác lần 1 để giống bài báo (10p+2h)",
    )
    ap.add_argument(
        "--beta",
        type=float,
        default=2.0,
        help="Hệ số bicriteria oracle (paper lý thuyết beta=2; implementation heuristic)",
    )
    ap.add_argument(
        "--no-local-search",
        action="store_true",
        help="Tắt mục 4 (2-opt + relocation sau Algorithm 2); mặc định vẫn chạy local search",
    )
    ap.add_argument("--out-dir", type=Path, default=Path("output_runs"), help="Thư mục kết quả + hình + log trace")
    ap.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="File log chi tiết thuật toán (mặc định: OUT_DIR/approx_algorithm.log)",
    )
    ap.add_argument(
        "--no-algorithm-log",
        action="store_true",
        help="Tắt ghi trace nhị phân / tham lam",
    )
    ap.add_argument("--verbose-mip", action="store_true")
    ap.add_argument(
        "--skip-mip",
        action="store_true",
        help="Chỉ chạy thuật toán bài báo (approx + local search); không gọi Gurobi / MIP",
    )
    ap.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Bật trace file ngay cả khi có --no-algorithm-log (tương thích app.py)",
    )
    args = ap.parse_args()

    algorithm_trace = (not args.no_algorithm_log) or args.verbose

    if args.instance:
        paths = args.instance
    else:
        inst_dir = _ROOT / "vrpcc" / "data" / "instances"
        paths = sorted(inst_dir.glob("*.json")) if inst_dir.is_dir() else []

    if not paths:
        print("Không có instance. Chạy: python -m vrpcc.data.generate_instances")
        sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if algorithm_trace:
        log_path = args.log_file if args.log_file is not None else args.out_dir / "approx_algorithm.log"
        configure_approx_trace_file(log_path, mode="w")
        print(f"Trace thuật toán → {log_path.resolve()}", flush=True)

    results: list[dict] = []
    use_ls = not args.no_local_search

    for p in paths:
        if p.name == "manifest.json":
            continue
        inst = VRPCCInstance.load_json(p)
        name = inst.name or p.stem

        approx_routes, approx_time, approx_obj, B = _run_approx(
            inst,
            args.beta,
            use_ls,
            algorithm_trace=algorithm_trace,
        )

        if args.skip_mip:
            row = {
                "name": name,
                "file": str(p),
                "approx_obj": approx_obj,
                "approx_time": approx_time,
                "B": B,
                "mip_skipped": True,
            }
            results.append(row)
            print(json.dumps(row, indent=2, ensure_ascii=False))
            if inst.coords is not None:
                plot_routes_map(
                    inst,
                    approx_routes,
                    args.out_dir / f"routes_paper_{name}.png",
                    title=f"Thuật toán bài báo (approx) — {name}",
                )
            continue

        from vrpcc.mip_gurobi import solve_vrpcc_mip

        r1 = solve_vrpcc_mip(inst, time_limit_sec=args.mip_limit_1, verbose=args.verbose_mip)
        mip_obj_1 = r1.obj
        mip_bound_1 = r1.bound
        mip_time_1 = r1.time_sec

        mip_obj_2 = mip_obj_1
        mip_bound_2 = mip_bound_1
        mip_time_2 = 0.0
        r2 = r1
        if args.mip_limit_2 and args.mip_limit_2 > 0 and args.mip_limit_2 != args.mip_limit_1:
            r2 = solve_vrpcc_mip(inst, time_limit_sec=args.mip_limit_2, verbose=args.verbose_mip)
            mip_obj_2 = r2.obj
            mip_bound_2 = r2.bound
            mip_time_2 = r2.time_sec

        lb2 = mip_bound_2
        ub2 = mip_obj_2
        row = {
            "name": name,
            "file": str(p),
            "approx_obj": approx_obj,
            "approx_time": approx_time,
            "B": B,
            "ratio_obj_lb2": (approx_obj / lb2) if lb2 and lb2 > 0 else None,
            "ratio_obj_ub2": (approx_obj / ub2) if ub2 and ub2 > 0 else None,
            "mip_status_1": r1.status,
            "mip_time_1": mip_time_1,
            "mip_obj_1": mip_obj_1,
            "mip_bound_1": mip_bound_1,
            "mip_status_2": r2.status,
            "mip_time_2": mip_time_2,
            "mip_obj_2": mip_obj_2,
            "mip_bound_2": mip_bound_2,
        }
        results.append(row)

        results[-1]["mip_time"] = mip_time_1
        results[-1]["mip_obj"] = mip_obj_1

        print(json.dumps(row, indent=2, ensure_ascii=False))

        if inst.coords is not None:
            plot_routes_map(
                inst,
                approx_routes,
                args.out_dir / f"routes_paper_{name}.png",
                title=f"Thuật toán bài báo (approx) — {name}",
            )
            if r1.routes:
                plot_routes_map(
                    inst,
                    r1.routes,
                    args.out_dir / f"routes_mip_reference_{name}.png",
                    title=f"MIP tham chiếu — {name}",
                )

    summary_path = args.out_dir / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Wrote", summary_path)

    plot_from_results_list(results, args.out_dir, include_mip=not args.skip_mip)


if __name__ == "__main__":
    main()
