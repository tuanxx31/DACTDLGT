

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app import _print_result
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



INSTANCE_PATHS = [
    "MIP/data_paper_101/tight/c-n21-k6/c-n21-k6.json",
    "MIP/data_paper_101/tight/r-n21-k6/r-n21-k6.json",
    "MIP/data_paper_101/tight/RC-n21-k6/RC-n21-k6.json",
]


INSTANCE_DIRS: list[str] = [

]

OUT_DIR = Path("output_selected_instances")
BETA = 5.0
EPS = 1e-3
USE_LOCAL_SEARCH = True
MAKE_PLOTS = True
WRITE_ALGORITHM_LOG = True


def _collect_json_files_recursive(root_dir: Path) -> list[Path]:
    if not root_dir.is_dir():
        return []
    return sorted(
        p for p in root_dir.rglob("*.json")
        if p.is_file() and p.name != "manifest.json"
    )


def _resolve_repo_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (_ROOT / p)


def _selected_instance_paths() -> list[Path]:
    paths = [_resolve_repo_path(p) for p in INSTANCE_PATHS]
    for d in INSTANCE_DIRS:
        paths.extend(_collect_json_files_recursive(_resolve_repo_path(d)))

    selected: list[Path] = []
    seen: set[Path] = set()
    for p in paths:
        rp = p.resolve()
        if rp in seen:
            continue
        selected.append(rp)
        seen.add(rp)
    return selected


def main() -> None:
    paths = _selected_instance_paths()
    if not paths:
        raise SystemExit("Chua co instance nao trong INSTANCE_PATHS / INSTANCE_DIRS.")

    missing = [p for p in paths if not p.is_file()]
    if missing:
        msg = "\n".join(str(p) for p in missing)
        raise SystemExit(f"Khong tim thay instance:\n{msg}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if WRITE_ALGORITHM_LOG:
        log_path = OUT_DIR / "approx_algorithm.log"
        configure_approx_trace_file(log_path, mode="w")
        print(f"Trace -> {log_path.resolve()}", flush=True)

    rows: list[dict] = []

    for p in paths:
        inst = VRPCCInstance.load_json(p)
        name = inst.name or p.stem

        oracle = make_oracle(inst, beta=BETA)
        observer = LoggingApproxObserver() if WRITE_ALGORITHM_LOG else NULL_OBSERVER
        observer.on_run_start(name)

        t_total_start = time.perf_counter()
        result = algorithm_2_vrpcc(
            inst,
            oracle,
            eps=EPS,
            beta=BETA,
            observer=observer,
        )

        if USE_LOCAL_SEARCH:
            routes_final = local_search(inst, result.routes)
            makespan_final = inst.makespan(routes_final)
        else:
            routes_final = result.routes
            makespan_final = result.makespan

        elapsed_total = time.perf_counter() - t_total_start
        _print_result(
            name,
            inst,
            result,
            routes_final,
            makespan_final,
            elapsed_total,
            USE_LOCAL_SEARCH,
        )

        rows.append(
            {
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
                "local_search": USE_LOCAL_SEARCH,
            }
        )

        if MAKE_PLOTS and inst.coords is not None:
            plot_routes_map(
                inst,
                routes_final,
                OUT_DIR / f"routes_paper_{name}.png",
                title=f"Thuat toan bai bao - {name}",
            )

    summary_path = OUT_DIR / "summary_selected_instances.json"
    summary_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Summary JSON -> {summary_path}")

    if MAKE_PLOTS and rows:
        plot_approx_only_bars(
            [str(r["name"]) for r in rows],
            [float(r["time_total"]) for r in rows],
            [float(r["makespan_final"]) for r in rows],
            OUT_DIR / "approx_bars.png",
        )


if __name__ == "__main__":
    main()
