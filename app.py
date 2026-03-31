#!/usr/bin/env python3
"""
Chạy riêng pipeline theo paper (Algorithm 1–2 + heuristic oracle lấy cảm hứng k-TSP, tuỳ chọn local search).
Không gọi MIP/Gurobi — dùng khi chỉ cần approx nhanh.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
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
from vrpcc.plotting import plot_approx_only_bars, plot_routes_map


def run_paper_algorithm(
    inst: VRPCCInstance,
    *,
    beta: float,
    use_local_search: bool,
    eps: float,
    algorithm_trace: bool = True,
) -> tuple[list[list[int]], float, float, float]:
    """
    Chạy pipeline trên một instance: heuristic oracle → Algorithm 2 → (tuỳ chọn) local search.

    Trả về:
        - routes: danh sách tuyến theo xe, mỗi tuyến là chuỗi đỉnh khép kín qua depot (0).
        - elapsed: thời gian chạy (giây), gồm cả local search nếu bật.
        - obj: giá trị makespan (max chi phí tuyến trên các xe).
        - B: ngân sách (cận trên khả thi) sau nhị phân trong Algorithm 2.

    Tham số:
        inst: bài toán VRPCC (ma trận khoảng cách, ma trận tương thích u).
        beta: hệ số bicriteria (mặc định 2 như lý thuyết paper; chi phí oracle ≤ beta × B khi có tuyến khả thi).
        use_local_search: True thì áp dụng mục 4 (2-opt theo đoạn + relocation).
        eps: độ chính xác binary search trên B trong Algorithm 2 (dừng khi upper−lower < eps).
        algorithm_trace: True thì ghi trace (file đã cấu hình bằng `configure_approx_trace_file` ở CLI).
    """
    oracle = make_oracle(inst, beta=beta)
    observer = LoggingApproxObserver() if algorithm_trace else NULL_OBSERVER
    t0 = time.perf_counter()
    observer.on_run_start(inst.name or "instance")
    routes, B = algorithm_2_vrpcc(inst, oracle, eps=eps, observer=observer)
    if use_local_search:
        routes = local_search(inst, routes)
    elapsed = time.perf_counter() - t0
    obj = inst.makespan(routes)
    return routes, elapsed, obj, B


def main() -> None:
    """
    Điểm vào CLI: đọc instance JSON, gọi run_paper_algorithm, in kết quả và (tuỳ chọn) lưu hình/summary.

    Tham số dòng lệnh được khai báo qua argparse (--instance, --beta, --no-local-search, ...).
    Không import hay gọi MIP/Gurobi.
    """
    ap = argparse.ArgumentParser(
        description="VRPCC: chỉ thuật toán bài báo (approx + local search), không MIP",
    )
    ap.add_argument(
        "--instance",
        type=Path,
        action="append",
        help="File JSON instance (lặp lại cho nhiều file). Mặc định: *.json trong vrpcc/data/instances",
    )
    ap.add_argument(
        "--beta",
        type=float,
        default=2.0,
        help="Hệ số bicriteria oracle (paper lý thuyết beta=2; oracle trong repo là heuristic)",
    )
    ap.add_argument(
        "--no-local-search",
        action="store_true",
        help="Tắt local search sau Algorithm 2",
    )
    ap.add_argument("--eps", type=float, default=1e-3, help="Ngưỡng binary search trên B")
    ap.add_argument("--out-dir", type=Path, default=Path("output_runs"), help="Kết quả JSON + hình + log trace")
    ap.add_argument("--no-plots", action="store_true", help="Không vẽ PNG")
    ap.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="File log chi tiết thuật toán (mặc định: OUT_DIR/approx_algorithm.log)",
    )
    ap.add_argument(
        "--no-algorithm-log",
        action="store_true",
        help="Tắt ghi trace nhị phân / tham lam (chỉ còn JSON ra stdout)",
    )
    ap.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Luôn ghi trace (ghi đè --no-algorithm-log nếu có)",
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
    log_path: Path | None = None
    if algorithm_trace:
        log_path = args.log_file if args.log_file is not None else args.out_dir / "approx_algorithm.log"
        configure_approx_trace_file(log_path, mode="w")
        print(f"Trace thuật toán (nhị phân + tham lam) → {log_path.resolve()}", flush=True)

    results: list[dict] = []
    use_ls = not args.no_local_search

    for p in paths:
        if p.name == "manifest.json":
            continue
        inst = VRPCCInstance.load_json(p)
        name = inst.name or p.stem
        routes, elapsed, obj, B = run_paper_algorithm(
            inst,
            beta=args.beta,
            use_local_search=use_ls,
            eps=args.eps,
            algorithm_trace=algorithm_trace,
        )
        row = {
            "name": name,
            "file": str(p),
            "approx_obj": obj,
            "approx_time": elapsed,
            "B": B,
            "beta": args.beta,
            "local_search": use_ls,
        }
        results.append(row)
        print(json.dumps(row, indent=2, ensure_ascii=False))

        if not args.no_plots and inst.coords is not None:
            plot_routes_map(
                inst,
                routes,
                args.out_dir / f"routes_paper_{name}.png",
                title=f"Thuật toán bài báo — {name}",
            )

    summary_path = args.out_dir / "summary_paper_only.json"
    summary_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Wrote", summary_path)

    if not args.no_plots and results:
        labels = [str(r["name"]) for r in results]
        plot_approx_only_bars(
            labels,
            [float(r["approx_time"]) for r in results],
            [float(r["approx_obj"]) for r in results],
            args.out_dir / "approx_bars.png",
        )


if __name__ == "__main__":
    main()
