#!/usr/bin/env python3
"""
One-click runner for paper-style VRPCC benchmark (small -> large) with live progress.

Default behavior:
- Dataset: MIP/data_paper_101
- Order:
    tight:   c/r/RC x (n21, n41, n61, n81, n101)
    relaxed: c/r/RC x (n21, n41, n61, n81, n101)
- MIP limits: 600s and 7200s
- Incremental save after each instance is handled by scripts/run_comparison.py
- Resume mode enabled by default (safe for long runs)
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def _ordered_instance_paths(data_root: Path) -> list[Path]:
    levels = ["tight", "relaxed"]
    sizes = ["21-k6", "41-k10", "61-k14", "81-k18", "101-k22"]
    layouts = ["c", "r", "RC"]

    paths: list[Path] = []
    missing: list[Path] = []
    for level in levels:
        # Run all tight instances from small to large first, then relaxed.
        # Within each size bucket, run C/R/RC in that order.
        for sz in sizes:
            for layout in layouts:
                name = f"{layout}-n{sz}"
                p = data_root / level / name / f"{name}.json"
                if p.is_file():
                    paths.append(p.resolve())
                else:
                    missing.append(p.resolve())

    if missing:
        msg = "\n".join(str(p) for p in missing[:20])
        extra = "" if len(missing) <= 20 else f"\n... and {len(missing) - 20} more"
        raise FileNotFoundError(
            f"Missing {len(missing)} instance files under {data_root}:\n{msg}{extra}"
        )
    return paths


def _read_summary(summary_path: Path) -> tuple[int, str | None]:
    if not summary_path.is_file():
        return 0, None
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return 0, None
        if not data:
            return 0, None
        last = data[-1]
        if isinstance(last, dict):
            last_name = last.get("Instance")
            return len(data), str(last_name) if isinstance(last_name, str) else None
        return len(data), None
    except Exception:
        return 0, None


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _default_python(repo_root: Path) -> Path:
    """
    Prefer repository venv interpreter so user can run this script without extra args.
    Fallback to current interpreter if venv is absent.
    """
    venv_py = repo_root / ".venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return venv_py
    return Path(sys.executable)


def _load_rows(summary_path: Path) -> list[dict]:
    if not summary_path.is_file():
        return []
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        return []
    except Exception:
        return []


def _has_python_env_mip_error(rows: list[dict]) -> bool:
    for r in rows:
        err = r.get("mip_error")
        if isinstance(err, str) and "No module named 'gurobipy'" in err:
            return True
    return False


def _fmt_csv_num(x: object) -> str:
    if x is None:
        return "-"
    try:
        return f"{float(x):.4f}"
    except Exception:
        return "-"


def _paper_order() -> list[str]:
    layouts = ["c", "r", "RC"]
    sizes = ["21-k6", "41-k10", "61-k14", "81-k18", "101-k22"]
    return [f"{lay}-n{sz}" for lay in layouts for sz in sizes]


def _level_from_file(file_path: str | None) -> str | None:
    if not file_path:
        return None
    fp = file_path.replace("\\", "/").lower()
    if "/tight/" in fp:
        return "tight"
    if "/relaxed/" in fp:
        return "relaxed"
    return None


def _export_paper_tables(out_dir: Path) -> tuple[Path, Path]:
    summary_path = out_dir / "summary.json"
    rows = _load_rows(summary_path)

    wanted_cols = [
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

    by_level_instance: dict[tuple[str, str], dict] = {}
    for r in rows:
        inst = r.get("Instance")
        lvl = _level_from_file(r.get("file") if isinstance(r.get("file"), str) else None)
        if isinstance(inst, str) and lvl in {"tight", "relaxed"}:
            by_level_instance[(lvl, inst)] = r

    def write_level(level: str, out_name: str) -> Path:
        out_path = out_dir / out_name
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=wanted_cols)
            w.writeheader()
            for inst in _paper_order():
                r = by_level_instance.get((level, inst), {})
                w.writerow(
                    {
                        "Instance": inst,
                        "LB1": _fmt_csv_num(r.get("LB1")),
                        "UB1": _fmt_csv_num(r.get("UB1")),
                        "Time_10min_s": _fmt_csv_num(r.get("Time_10min_s")),
                        "LB2": _fmt_csv_num(r.get("LB2")),
                        "UB2": _fmt_csv_num(r.get("UB2")),
                        "Time_2hours_s": _fmt_csv_num(r.get("Time_2hours_s")),
                        "Obj": _fmt_csv_num(r.get("Obj")),
                        "Time_algo_s": _fmt_csv_num(r.get("Time_algo_s")),
                        "Obj_over_LB2": _fmt_csv_num(r.get("Obj_over_LB2")),
                        "Obj_over_UB2": _fmt_csv_num(r.get("Obj_over_UB2")),
                    }
                )
        return out_path

    t1 = write_level("tight", "table1_tight_like_paper.csv")
    t2 = write_level("relaxed", "table2_relaxed_like_paper.csv")
    return t1, t2


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run paper-style benchmark with progress monitor and resume support."
    )
    ap.add_argument(
        "--data-root",
        type=Path,
        default=Path("MIP/data_paper_101"),
        help="Root of paper-style JSON instances (default: MIP/data_paper_101)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("output_paper_101_benchmark_small_to_large"),
        help="Output directory for CSV/JSON/logs",
    )
    ap.add_argument(
        "--mip-limit-1",
        type=float,
        default=600.0,
        help="MIP time limit 1 (seconds), default 600",
    )
    ap.add_argument(
        "--mip-limit-2",
        type=float,
        default=7200.0,
        help="MIP time limit 2 (seconds), default 7200",
    )
    ap.add_argument(
        "--interval-sec",
        type=float,
        default=20.0,
        help="Progress print interval in seconds (default 20)",
    )
    ap.add_argument(
        "--max-instances",
        type=int,
        default=0,
        help="Optional debug limit: run only first N instances (0 = all)",
    )
    ap.add_argument(
        "--python",
        type=Path,
        default=None,
        help="Python executable to run child benchmark process (default: .venv/Scripts/python.exe if exists)",
    )
    ap.add_argument(
        "--verbose-mip",
        action="store_true",
        help="Pass --verbose-mip to run_comparison.py",
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    data_root = (repo_root / args.data_root).resolve() if not args.data_root.is_absolute() else args.data_root.resolve()
    out_dir = (repo_root / args.out_dir).resolve() if not args.out_dir.is_absolute() else args.out_dir.resolve()
    run_script = repo_root / "scripts" / "run_comparison.py"
    py_exe = args.python.resolve() if args.python is not None else _default_python(repo_root).resolve()

    if not run_script.is_file():
        raise FileNotFoundError(f"Cannot find benchmark script: {run_script}")
    if not py_exe.is_file():
        raise FileNotFoundError(f"Python executable not found: {py_exe}")

    # Early check: child interpreter must have gurobipy for MIP benchmark.
    chk = subprocess.run(
        [str(py_exe), "-c", "import importlib.util as u; print(bool(u.find_spec('gurobipy')))"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    has_gurobi = chk.returncode == 0 and chk.stdout.strip().lower() == "true"
    if not has_gurobi:
        raise RuntimeError(
            "Selected Python does not have gurobipy. "
            f"Interpreter: {py_exe}\n"
            "Activate/install gurobipy in this interpreter, or pass --python explicitly."
        )

    paths = _ordered_instance_paths(data_root)
    if args.max_instances > 0:
        paths = paths[: args.max_instances]

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.json"
    csv_path = out_dir / "comparison_table.csv"
    stdout_log = out_dir / "runner_stdout.log"
    stderr_log = out_dir / "runner_stderr.log"

    # Guard against reusing corrupted outputs from a wrong Python environment
    # (for example when previous runs had `No module named 'gurobipy'`).
    existing_rows = _load_rows(summary_path)
    if existing_rows and _has_python_env_mip_error(existing_rows):
        backup = out_dir.with_name(
            f"{out_dir.name}_auto_backup_bad_env_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        out_dir.rename(backup)
        out_dir.mkdir(parents=True, exist_ok=True)
        print(
            f"[{_timestamp()}] Found previous invalid MIP rows (missing gurobipy). "
            f"Moved old output to: {backup}"
        )
        summary_path = out_dir / "summary.json"
        csv_path = out_dir / "comparison_table.csv"
        stdout_log = out_dir / "runner_stdout.log"
        stderr_log = out_dir / "runner_stderr.log"

    cmd = [
        str(py_exe),
        "-u",
        str(run_script),
        "--mip-limit-1",
        str(args.mip_limit_1),
        "--mip-limit-2",
        str(args.mip_limit_2),
        "--out-dir",
        str(out_dir),
        "--resume",
    ]
    if args.verbose_mip:
        cmd.append("--verbose-mip")
    for p in paths:
        cmd.extend(["--instance", str(p)])

    print(f"[{_timestamp()}] Starting benchmark")
    print(f"  data_root : {data_root}")
    print(f"  out_dir   : {out_dir}")
    print(f"  total     : {len(paths)} instances")
    print(f"  command   : {' '.join(cmd[:8])} ...")
    print(f"  stdout log: {stdout_log}")
    print(f"  stderr log: {stderr_log}")
    print("")

    # Create the two paper-style tables immediately, even before the first
    # instance finishes, so partial progress is always visible on disk.
    t1, t2 = _export_paper_tables(out_dir)
    print(f"[{_timestamp()}] initialized table1 -> {t1}")
    print(f"[{_timestamp()}] initialized table2 -> {t2}")

    with stdout_log.open("a", encoding="utf-8") as out_f, stderr_log.open("a", encoding="utf-8") as err_f:
        proc = subprocess.Popen(
            cmd,
            cwd=str(repo_root),
            stdout=out_f,
            stderr=err_f,
            text=True,
        )

        prev_done = -1
        ordered_names = [p.stem for p in paths]
        while True:
            rc = proc.poll()
            done, last = _read_summary(summary_path)

            # Print when progress changes or periodic heartbeat.
            if done != prev_done:
                prev_done = done
                t1, t2 = _export_paper_tables(out_dir)
                pct = (100.0 * done / len(paths)) if paths else 100.0
                next_name = ordered_names[done] if done < len(ordered_names) else "-"
                print(
                    f"[{_timestamp()}] done {done}/{len(paths)} ({pct:.1f}%) | "
                    f"last={last or '-'} | next={next_name}"
                )
                print(f"[{_timestamp()}] updated table1 -> {t1}")
                print(f"[{_timestamp()}] updated table2 -> {t2}")

            if rc is not None:
                break
            time.sleep(max(1.0, args.interval_sec))

        done, last = _read_summary(summary_path)
        pct = (100.0 * done / len(paths)) if paths else 100.0
        print("")
        print(f"[{_timestamp()}] Benchmark finished with exit code {rc}")
        print(f"  completed : {done}/{len(paths)} ({pct:.1f}%)")
        print(f"  last      : {last or '-'}")
        print(f"  summary   : {summary_path}")
        print(f"  csv       : {csv_path}")
        t1, t2 = _export_paper_tables(out_dir)
        print(f"  table1    : {t1}")
        print(f"  table2    : {t2}")
        if rc != 0:
            print(f"  stderr log: {stderr_log}")
            sys.exit(rc)


if __name__ == "__main__":
    main()
