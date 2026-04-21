#!/usr/bin/env python3
"""
Chạy VRPCC từ file: sửa INSTANCE_JSON bên dưới, rồi: python vrpcc.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# --- Chỉnh đường dẫn instance tại đây (tương đối gốc repo hoặc đường dẫn tuyệt đối) ---
INSTANCE_JSON = "MIP/data_paper_101/tight/c-n21-k6/c-n21-k6.json"
# Muốn chạy cả thư mục: đặt INSTANCE_JSON = None và chỉnh INSTANCE_DIR (hoặc để None = tight mặc định).
INSTANCE_DIR: str | Path | None = None
_DEFAULT_FALLBACK_DIR = Path("MIP") / "data_paper_101" / "tight"

BETA = 5.0
EPS = 1e-3
OUT_DIR = Path("output_runs")
USE_LOCAL_SEARCH = True
MAKE_PLOTS = True
ALGORITHM_TRACE = True
LOG_FILE: Path | None = None
VERBOSE = False

# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app import (  # noqa: E402
    _collect_json_files_recursive,
    _print_result,
)
from vrpcc.approx_algorithm import algorithm_2_vrpcc  # noqa: E402
from vrpcc.approx_observer import NULL_OBSERVER  # noqa: E402
from vrpcc.approx_observer_logging import (  # noqa: E402
    LoggingApproxObserver,
    configure_approx_trace_file,
)
from vrpcc.instance import VRPCCInstance  # noqa: E402
from vrpcc.k_tsp_oracle import make_oracle  # noqa: E402
from vrpcc.local_search import local_search  # noqa: E402
from vrpcc.plotting import plot_approx_only_bars, plot_routes_map  # noqa: E402


def _resolve_path(p: str | Path) -> Path:
    pp = Path(p)
    return pp if pp.is_absolute() else (_ROOT / pp)


def _gather_instance_paths() -> list[Path]:
    if INSTANCE_JSON is not None and str(INSTANCE_JSON).strip():
        return [_resolve_path(INSTANCE_JSON).resolve()]
    root = _resolve_path(INSTANCE_DIR) if INSTANCE_DIR else _resolve_path(_DEFAULT_FALLBACK_DIR)
    paths = _collect_json_files_recursive(root)
    return sorted({p.resolve() for p in paths})


def main() -> None:
    algorithm_trace = ALGORITHM_TRACE or VERBOSE
    paths = _gather_instance_paths()

    if not paths:
        print("Không thấy file .json — kiểm tra INSTANCE_JSON hoặc thư mục trong INSTANCE_DIR / data_paper_101/tight.")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if algorithm_trace:
        log_path = LOG_FILE if LOG_FILE is not None else OUT_DIR / "approx_algorithm.log"
        configure_approx_trace_file(log_path, mode="w")
        print(f"Trace → {log_path.resolve()}", flush=True)

    results_json: list[dict] = []
    use_ls = USE_LOCAL_SEARCH

    for p in paths:
        if p.name == "manifest.json":
            continue
        inst = VRPCCInstance.load_json(p)
        name = inst.name or p.stem

        oracle = make_oracle(inst, beta=BETA)
        observer = LoggingApproxObserver() if algorithm_trace else NULL_OBSERVER
        observer.on_run_start(name)

        t_total_start = time.perf_counter()
        result = algorithm_2_vrpcc(
            inst, oracle, eps=EPS, beta=BETA, observer=observer,
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
            "beta": BETA,
            "eps": EPS,
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

        if MAKE_PLOTS and inst.coords is not None:
            plot_routes_map(
                inst, routes_final,
                OUT_DIR / f"routes_paper_{name}.png",
                title=f"Thuật toán bài báo — {name}",
            )

    summary_path = OUT_DIR / "summary_paper_only.json"
    summary_path.write_text(json.dumps(results_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Summary JSON → {summary_path}")

    if MAKE_PLOTS and results_json:
        labels = [str(r["name"]) for r in results_json]
        plot_approx_only_bars(
            labels,
            [float(r["time_total"]) for r in results_json],
            [float(r["makespan_final"]) for r in results_json],
            OUT_DIR / "approx_bars.png",
        )


if __name__ == "__main__":
    main()
