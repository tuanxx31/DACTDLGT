"""
VRPCC (Yu, Nagarajan, Shen 2018) — MIP min makespan tau.

Tham số (input) theo bài báo:
  - c[i][j]: chi phí cạnh (khoảng cách).
  - u[k][i] tuong ung u^k_i: =1 neu xe k duoc phuc vu tai nut i (khach); kho i=0 luon 1.
  - n, m: so nut, so xe.

Output toi uu: tau (makespan); bien x^k_ij trong solver.

Hai thu muc du lieu tho (chi khac do chat cua u):
  - data/   tuong thich chat
  - data2/  tuong thich thoang hon

main_data.py  -> chi data/
main_data2.py -> chi data2/
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import pulp as pl


@dataclass
class SolveResult:
    name: str
    status: str
    objective: Optional[float]
    tau: Optional[float]
    time_sec: float
    iterations: int
    message: str
    stop_reason: str = ""


def load_instance(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _xk_values(
    x: Dict[Tuple[int, int, int], pl.LpVariable], k: int, n: int
) -> List[List[float]]:
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if (k, i, j) in x:
                v = x[(k, i, j)].value()
                mat[i][j] = float(v) if v is not None else 0.0
    return mat


def find_subtour_customer_set(
    xk: List[List[float]], n: int, tol: float = 0.5
) -> Optional[Set[int]]:
    used: Set[int] = set()
    for i in range(n):
        for j in range(n):
            if i != j and xk[i][j] > tol:
                used.add(i)
                used.add(j)
    if not used:
        return None
    reach: Set[int] = {0}
    stack = [0]
    while stack:
        v = stack.pop()
        for w in range(n):
            if xk[v][w] > tol and w not in reach:
                reach.add(w)
                stack.append(w)
    viol = used - reach
    viol.discard(0)
    if not viol:
        return None
    start = min(viol)
    comp: Set[int] = set()
    stack2 = [start]
    while stack2:
        v = stack2.pop()
        if v in comp:
            continue
        comp.add(v)
        for w in range(n):
            if w in viol and w != v and xk[v][w] > tol:
                stack2.append(w)
            if w in viol and w != v and xk[w][v] > tol:
                stack2.append(w)
    cust = {v for v in comp if v > 0}
    return cust if len(cust) >= 2 else None


def build_model_base(
    c: List[List[float]],
    u: List[List[int]],
    m: int,
    n: int,
) -> Tuple[pl.LpProblem, Dict[Tuple[int, int, int], pl.LpVariable], pl.LpVariable]:
    prob = pl.LpProblem("VRPCC_makespan", pl.LpMinimize)
    tau = pl.LpVariable("tau", lowBound=0, cat=pl.LpContinuous)

    x: Dict[Tuple[int, int, int], pl.LpVariable] = {}
    for k in range(m):
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if j > 0 and u[k][j] == 0:
                    continue
                if i > 0 and u[k][i] == 0:
                    continue
                x[(k, i, j)] = pl.LpVariable(f"x_{k}_{i}_{j}", cat=pl.LpBinary)

    prob += tau

    for k in range(m):
        prob += (
            pl.lpSum(
                c[i][j] * x[(k, i, j)]
                for i in range(n)
                for j in range(n)
                if (k, i, j) in x
            )
            <= tau,
            f"maxlen_{k}",
        )

    for k in range(m):
        prob += (
            pl.lpSum(x[(k, 0, j)] for j in range(n) if (k, 0, j) in x) == 1,
            f"leave_depot_{k}",
        )

    for k in range(m):
        for v in range(n):
            lin = [x[(k, i, v)] for i in range(n) if i != v and (k, i, v) in x]
            lout = [x[(k, v, j)] for j in range(n) if j != v and (k, v, j) in x]
            prob += pl.lpSum(lin) - pl.lpSum(lout) == 0, f"flow_{k}_{v}"

    for j in range(1, n):
        prob += (
            pl.lpSum(
                x[(k, i, j)]
                for k in range(m)
                for i in range(n)
                if i != j and (k, i, j) in x
            )
            == 1,
            f"visit_{j}",
        )

    for k in range(m):
        for j in range(1, n):
            if u[k][j] == 0:
                continue
            for i in range(n):
                if i == j:
                    continue
                if (k, i, j) in x:
                    prob += x[(k, i, j)] <= u[k][j], f"comp_{k}_{i}_{j}"

    for k in range(m):
        for i in range(1, n):
            for j in range(i + 1, n):
                if (k, i, j) in x and (k, j, i) in x:
                    prob += (
                        x[(k, i, j)] + x[(k, j, i)] <= 1,
                        f"two_{k}_{i}_{j}",
                    )

    return prob, x, tau


def _has_integer_x(
    x: Dict[Tuple[int, int, int], pl.LpVariable], tol: float = 1e-5
) -> bool:
    for v in x.values():
        val = v.value()
        if val is None:
            return False
        if abs(val - round(val)) > tol:
            return False
    return True


def solve_vrpcc(
    inst: dict,
    time_budget_sec: int = 300,
    max_iters: int = 30,
    per_solve_cap_sec: int = 90,
    verbose: bool = True,
) -> SolveResult:
    name = inst["name"]
    n = inst["n"]
    m = inst["m"]
    c = inst["c"]
    u = inst["u"]
    t0 = time.perf_counter()

    prob, x, tau = build_model_base(c, u, m, n)
    it = 0
    last_msg = ""

    while it < max_iters:
        it += 1
        elapsed = time.perf_counter() - t0
        remain = time_budget_sec - elapsed
        if remain < 3:
            if verbose:
                print(
                    f"  [{name}] het ngan sach ({time_budget_sec}s) sau {it - 1} vong.",
                    flush=True,
                )
            return SolveResult(
                name=name,
                status="TimeBudget",
                objective=float(pl.value(tau)) if tau.value() is not None else None,
                tau=float(pl.value(tau)) if tau.value() is not None else None,
                time_sec=time.perf_counter() - t0,
                iterations=it - 1,
                message=last_msg or "Het thoi gian tong (time_budget_sec).",
                stop_reason="budget",
            )
        tl = max(5, int(min(per_solve_cap_sec, remain)))
        if verbose:
            print(
                f"  [{name}] vong SEC {it}: goi CBC toi da {tl}s "
                f"(con lai ~{remain:.0f}s)...",
                flush=True,
            )
        t_solve = time.perf_counter()
        solver = pl.PULP_CBC_CMD(msg=False, timeLimit=tl)
        try:
            prob.solve(solver)
        except KeyboardInterrupt:
            if verbose:
                print(
                    f"\n  [{name}] Dung bang Ctrl+C trong luc CBC dang chay "
                    f"(doi toi {tl}s hoac ket thuc som). Khong phai loi code.",
                    flush=True,
                )
            raise
        solve_sec = time.perf_counter() - t_solve
        status = pl.LpStatus[prob.status]

        ok = prob.status in (pl.LpStatusOptimal,) or (
            tau.value() is not None and _has_integer_x(x)
        )

        if verbose:
            tv = pl.value(tau)
            print(
                f"  [{name}]   xong sau {solve_sec:.1f}s, status={status}, tau~={tv}",
                flush=True,
            )

        if not ok:
            obj = pl.value(tau) if tau.value() is not None else None
            return SolveResult(
                name=name,
                status=status,
                objective=float(obj) if obj is not None else None,
                tau=float(obj) if obj is not None else None,
                time_sec=time.perf_counter() - t0,
                iterations=it,
                message=last_msg or f"Không có nghiệm nguyên hợp lệ: {status}",
                stop_reason="no_integer",
            )

        cuts_added = 0
        for k in range(m):
            xk = _xk_values(x, k, n)
            S = find_subtour_customer_set(xk, n)
            if S is None or len(S) < 2:
                continue
            nodes = sorted(S)
            ssum = pl.lpSum(
                x[(k, i, j)]
                for i in nodes
                for j in nodes
                if i != j and (k, i, j) in x
            )
            prob += ssum <= len(S) - 1, f"sec_{it}_{k}_{'_'.join(map(str, nodes))}"
            cuts_added += 1

        if cuts_added == 0:
            obj = float(pl.value(tau))
            gap_note = ""
            if prob.status != pl.LpStatusOptimal:
                gap_note = " (CBC có thể chưa chứng minh tối ưu toàn cục)."
            return SolveResult(
                name=name,
                status=status,
                objective=obj,
                tau=obj,
                time_sec=time.perf_counter() - t0,
                iterations=it,
                message=f"Không còn subtour.{gap_note}",
                stop_reason="ok",
            )

        last_msg = f"Lần {it}: thêm {cuts_added} SEC."
        if verbose:
            print(f"  [{name}]   them {cuts_added} cat SEC, giai lai...", flush=True)

    obj = pl.value(tau)
    return SolveResult(
        name=name,
        status="MaxIterations",
        objective=float(obj) if obj is not None else None,
        tau=float(obj) if obj is not None else None,
        time_sec=time.perf_counter() - t0,
        iterations=it,
        message=last_msg or f"Het {max_iters} vong SEC (tang max_iters hoac time_budget).",
        stop_reason="max_iters",
    )


def solve_folder(
    folder: str,
    time_budget_sec: int = 300,
    per_solve_cap_sec: int = 90,
    max_iters: int = 30,
    verbose: bool = True,
) -> List[SolveResult]:
    base = os.path.dirname(os.path.abspath(__file__))
    dpath = os.path.join(base, folder)
    names = ["C-n21-k6.json", "R-n21-k6.json", "RC-n21-k6.json"]
    results: List[SolveResult] = []
    for fn in names:
        p = os.path.join(dpath, fn)
        if not os.path.isfile(p):
            raise FileNotFoundError(p)
        inst = load_instance(p)
        if verbose:
            print(f"\n=== {inst['name']} ===", flush=True)
        results.append(
            solve_vrpcc(
                inst,
                time_budget_sec=time_budget_sec,
                per_solve_cap_sec=per_solve_cap_sec,
                max_iters=max_iters,
                verbose=verbose,
            )
        )
    return results
