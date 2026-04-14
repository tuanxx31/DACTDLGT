#!/usr/bin/env python3
"""
VRPCC: thuật toán bài báo (mục 3–4) + tuỳ chọn MIP so sánh.

Mặc định gói nhanh (~≤2 phút với instance nhỏ trong vrpcc/data/instances): MIP 40s/instance, không chạy MIP lần 2.
--skip-mip: chỉ approx (+ local search), không Gurobi (vài giây).
--mip-limit-1 / --mip-limit-2: tăng khi cần thử nghiệm giống bài báo.
"""

from __future__ import annotations

import argparse
import csv
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


def _collect_json_files_recursive(root_dir: Path) -> list[Path]:
    """Lấy toàn bộ JSON trong thư mục (đệ quy), bỏ qua manifest."""
    if not root_dir.is_dir():
        return []
    return sorted(
        p for p in root_dir.rglob("*.json")
        if p.is_file() and p.name != "manifest.json"
    )


def _to_float_or_none(x: object) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _fmt_csv_num(x: float | None) -> str:
    if x is None:
        return "-"
    return f"{x:.4f}"


def _collect_default_light_instances(root: Path) -> list[Path]:
    """
    Mặc định test nhanh nhóm nhẹ nhất trong paper: *-n21-k6.
    Ưu tiên thư mục MIP/data, fallback về vrpcc/data/instances.
    """
    candidates = _collect_json_files_recursive(root / "MIP" / "data")
    light = [p for p in candidates if "n21-k6" in p.stem.lower()]
    if light:
        return sorted(light)

    candidates = _collect_json_files_recursive(root / "vrpcc" / "data" / "instances")
    light = [p for p in candidates if "n21-k6" in p.stem.lower()]
    return sorted(light)


def _write_comparison_csv(rows: list[dict], out_csv: Path) -> None:
    headers = [
        "Instance",
        "LB1",
        "UB1",
        "Time_10min_s",
        "LB2",
        "UB2",
        "Time_2hours_s",
        "Obj",
        "Time_algo_s",
        "Obj_over_LB2",
        "Obj_over_UB2",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "Instance": r["Instance"],
                "LB1": _fmt_csv_num(r["LB1"]),
                "UB1": _fmt_csv_num(r["UB1"]),
                "Time_10min_s": _fmt_csv_num(r["Time_10min_s"]),
                "LB2": _fmt_csv_num(r["LB2"]),
                "UB2": _fmt_csv_num(r["UB2"]),
                "Time_2hours_s": _fmt_csv_num(r["Time_2hours_s"]),
                "Obj": _fmt_csv_num(r["Obj"]),
                "Time_algo_s": _fmt_csv_num(r["Time_algo_s"]),
                "Obj_over_LB2": _fmt_csv_num(r["Obj_over_LB2"]),
                "Obj_over_UB2": _fmt_csv_num(r["Obj_over_UB2"]),
            })


def _flush_incremental_outputs(out_dir: Path, rows: list[dict]) -> None:
    """
    Ghi ket qua trung gian sau moi instance de co CSV/JSON ngay lap tuc.
    """
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    csv_path = out_dir / "comparison_table.csv"
    _write_comparison_csv(rows, csv_path)


def _solve_mip_report_from_mip_module(
    instance_path: Path,
    time_limit_sec: float,
    verbose: bool,
) -> tuple[str, float | None, float | None, float]:
    """
    Dùng solver MIP gốc trong thư mục MIP (sparse arcs) để giảm kích thước model
    so với solver vrpcc/mip_gurobi.py.
    Trả về: (status, lb, ub, time_sec).
    """
    mip_dir = _ROOT / "MIP"
    if str(mip_dir) not in sys.path:
        sys.path.insert(0, str(mip_dir))
    from instancegen import load_instance  # type: ignore
    from vrpcc_mip import solve_vrpcc  # type: ignore

    inst_mip = load_instance(str(instance_path))
    rep = solve_vrpcc(inst_mip, time_limit=float(time_limit_sec), verbose=bool(verbose))
    return _status_name_mip_report(rep.status), _to_float_or_none(rep.lb), _to_float_or_none(rep.ub), float(rep.time_sec)


def _status_name_mip_report(status_code: int) -> str:
    try:
        import gurobipy as gp  # type: ignore
    except Exception:
        return str(status_code)
    names = {
        gp.GRB.LOADED: "LOADED",
        gp.GRB.OPTIMAL: "OPTIMAL",
        gp.GRB.INFEASIBLE: "INFEASIBLE",
        gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
        gp.GRB.UNBOUNDED: "UNBOUNDED",
        gp.GRB.CUTOFF: "CUTOFF",
        gp.GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
        gp.GRB.NODE_LIMIT: "NODE_LIMIT",
        gp.GRB.TIME_LIMIT: "TIME_LIMIT",
        gp.GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
        gp.GRB.INTERRUPTED: "INTERRUPTED",
        gp.GRB.NUMERIC: "NUMERIC",
        gp.GRB.SUBOPTIMAL: "SUBOPTIMAL",
        gp.GRB.INPROGRESS: "INPROGRESS",
        gp.GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT",
    }
    return names.get(status_code, str(status_code))


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
    result = algorithm_2_vrpcc(inst, oracle, eps=1e-3, beta=beta, observer=observer)
    routes = result.routes
    if use_ls:
        routes = local_search(inst, routes)
    elapsed = time.perf_counter() - t0
    route_costs = [inst.tour_length(r, k) if len(r) >= 2 else 0.0 for k, r in enumerate(routes)]
    obj = max(route_costs) if route_costs else 0.0
    return routes, elapsed, obj, result.B_upper


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
        "--instance-dir",
        type=Path,
        action="append",
        help="Thư mục chứa JSON instance (quét đệ quy, ví dụ: MIP/data, MIP/data2)",
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
        default=5.0,
        help="Hệ số bicriteria oracle (paper thực nghiệm dùng k-TSP 5-approx; cận tốt nhất lý thuyết là beta=2)",
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
        help="Chỉ chạy thuật toán bài báo (approx + local search), bỏ MIP tham chiếu",
    )
    ap.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Bật trace file ngay cả khi có --no-algorithm-log (tương thích app.py)",
    )
    ap.add_argument(
        "--all-instances",
        action="store_true",
        help="Nếu bật, chạy toàn bộ instance tìm thấy. Mặc định chạy nhóm nhẹ n21-k6.",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Tiếp tục từ OUT_DIR/summary.json: bỏ qua instance đã có kết quả.",
    )
    args = ap.parse_args()

    algorithm_trace = (not args.no_algorithm_log) or args.verbose

    paths: list[Path] = []
    if args.instance:
        for p in args.instance:
            pp = p if p.is_absolute() else (_ROOT / p)
            if pp.is_dir():
                paths.extend(_collect_json_files_recursive(pp))
            else:
                paths.append(pp)
    if args.instance_dir:
        for d in args.instance_dir:
            dd = d if d.is_absolute() else (_ROOT / d)
            paths.extend(_collect_json_files_recursive(dd))
    if not paths:
        if args.all_instances:
            inst_dir = _ROOT / "vrpcc" / "data" / "instances"
            paths = _collect_json_files_recursive(inst_dir)
        else:
            paths = _collect_default_light_instances(_ROOT)

    if not paths:
        print("Không có instance. Chạy: python -m vrpcc.data.generate_instances")
        sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.out_dir / "summary.json"

    existing_rows: list[dict] = []
    done_files: set[str] = set()
    if args.resume and summary_path.is_file():
        try:
            loaded = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                for row in loaded:
                    if isinstance(row, dict):
                        existing_rows.append(row)
                        f = row.get("file")
                        if isinstance(f, str) and f:
                            try:
                                done_files.add(str(Path(f).resolve()))
                            except Exception:
                                done_files.add(f)
                if existing_rows:
                    print(
                        f"Resume mode: loaded {len(existing_rows)} rows from {summary_path.resolve()}",
                        flush=True,
                    )
        except Exception as exc:
            print(f"Warning: cannot load resume file {summary_path}: {exc}", flush=True)

    if done_files:
        filtered: list[Path] = []
        skipped = 0
        for p in paths:
            rp = str(p.resolve())
            if rp in done_files:
                skipped += 1
                continue
            filtered.append(p)
        paths = filtered
        if skipped:
            print(f"Resume mode: skipped {skipped} completed instances", flush=True)

    if algorithm_trace:
        log_path = args.log_file if args.log_file is not None else args.out_dir / "approx_algorithm.log"
        log_mode = "a" if args.resume and log_path.exists() else "w"
        configure_approx_trace_file(log_path, mode=log_mode)
        print(f"Trace algorithm ({log_mode}) -> {log_path.resolve()}", flush=True)

    results: list[dict] = list(existing_rows)
    use_ls = not args.no_local_search

    if not paths:
        print("Không còn instance mới để chạy (resume hoàn tất).")
        _flush_incremental_outputs(args.out_dir, results)
        print("Wrote", summary_path)
        print("Wrote", args.out_dir / "comparison_table.csv")
        return

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
                "Instance": name,
                "LB1": None,
                "UB1": None,
                "Time_10min_s": None,
                "LB2": None,
                "UB2": None,
                "Time_2hours_s": None,
                "Obj": approx_obj,
                "Time_algo_s": approx_time,
                "Obj_over_LB2": None,
                "Obj_over_UB2": None,
                "file": str(p),
                "B": B,
                "mip_skipped": True,
                # Backward compatibility for plotting utility
                "approx_obj": approx_obj,
                "approx_time": approx_time,
            }
            results.append(row)
            print(json.dumps(row, indent=2, ensure_ascii=False))
            _flush_incremental_outputs(args.out_dir, results)
            if inst.coords is not None:
                plot_routes_map(
                    inst,
                    approx_routes,
                    args.out_dir / f"routes_paper_{name}.png",
                    title=f"Thuật toán bài báo (approx) — {name}",
                )
            continue

        # Ưu tiên solver MIP trong thư mục MIP để khớp benchmark paper và tránh model quá lớn.
        # Nếu một instance vượt license giới hạn kích thước, giữ batch chạy tiếp.
        status1 = "SKIPPED"
        status2 = "SKIPPED"
        mip_bound_1 = None
        mip_obj_1 = None
        mip_time_1 = None
        mip_bound_2 = None
        mip_obj_2 = None
        mip_time_2 = None
        mip_error = None
        try:
            status1, mip_bound_1, mip_obj_1, mip_time_1 = _solve_mip_report_from_mip_module(
                p,
                time_limit_sec=float(args.mip_limit_1),
                verbose=bool(args.verbose_mip),
            )
            status2 = status1
            mip_obj_2 = mip_obj_1
            mip_bound_2 = mip_bound_1
            mip_time_2 = mip_time_1
            if args.mip_limit_2 and args.mip_limit_2 > 0 and args.mip_limit_2 != args.mip_limit_1:
                status2, mip_bound_2, mip_obj_2, mip_time_2 = _solve_mip_report_from_mip_module(
                    p,
                    time_limit_sec=float(args.mip_limit_2),
                    verbose=bool(args.verbose_mip),
                )
        except Exception as exc:  # keep robust batch export
            mip_error = str(exc)
            status1 = "MIP_ERROR"
            status2 = "MIP_ERROR"

        lb1 = _to_float_or_none(mip_bound_1)
        ub1 = _to_float_or_none(mip_obj_1)
        lb2 = _to_float_or_none(mip_bound_2)
        ub2 = _to_float_or_none(mip_obj_2)
        row = {
            "Instance": name,
            "LB1": lb1,
            "UB1": ub1,
            "Time_10min_s": _to_float_or_none(mip_time_1),
            "LB2": lb2,
            "UB2": ub2,
            "Time_2hours_s": _to_float_or_none(mip_time_2),
            "Obj": _to_float_or_none(approx_obj),
            "Time_algo_s": _to_float_or_none(approx_time),
            "Obj_over_LB2": (approx_obj / lb2) if lb2 and lb2 > 0 else None,
            "Obj_over_UB2": (approx_obj / ub2) if ub2 and ub2 > 0 else None,
            "file": str(p),
            "B": B,
            "mip_status_1": status1,
            "mip_status_2": status2,
            "mip_error": mip_error,
            # Backward compatibility for plotting utility
            "approx_obj": approx_obj,
            "approx_time": approx_time,
            "mip_time": mip_time_1,
            "mip_obj": mip_obj_1,
        }
        results.append(row)

        print(json.dumps(row, indent=2, ensure_ascii=False))
        _flush_incremental_outputs(args.out_dir, results)

        if inst.coords is not None:
            plot_routes_map(
                inst,
                approx_routes,
                args.out_dir / f"routes_paper_{name}.png",
                title=f"Thuật toán bài báo (approx) — {name}",
            )

    csv_path = args.out_dir / "comparison_table.csv"
    print("Wrote", summary_path)
    print("Wrote", csv_path)

    try:
        plot_from_results_list(results, args.out_dir, include_mip=not args.skip_mip)
    except Exception as exc:
        print(f"Skip plotting due to incompatible/partial rows: {exc}")


if __name__ == "__main__":
    main()
