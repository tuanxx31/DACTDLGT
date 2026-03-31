"""
MIP (1)-(8) Yu et al. — lazy subtour elimination (7).

Vai trò: chuẩn tham chiếu (UB/LB, thời gian solver). Không phải đối tượng nghiên cứu chính.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import gurobipy as gp
import numpy as np
from gurobipy import GRB

if TYPE_CHECKING:
    from vrpcc.instance import VRPCCInstance


@dataclass
class MIPResult:
    status: str
    obj: float | None
    bound: float | None
    time_sec: float
    routes: list[list[int]] | None
    mip_gap: float | None


def _extract_succ(vals: np.ndarray, k: int, n: int, tol: float = 0.5) -> dict[int, int]:
    """One successor per i: argmax_j x[k,i,j] when row has positive mass (robust at MIPSOL)."""
    succ: dict[int, int] = {}
    for i in range(n):
        row = vals[k, i, :]
        j_star = int(np.argmax(row))
        if row[j_star] > tol:
            succ[i] = j_star
    return succ


def _two_customer_cycle(vals: np.ndarray, k: int, v0: int, n: int, tol: float = 0.5) -> list[int] | None:
    for j in range(1, n):
        if j != v0 and vals[k, v0, j] > tol and vals[k, j, v0] > tol:
            return sorted({v0, j})
    return None


def _customers_served_by_vehicle(vals: np.ndarray, k: int, n: int, tol: float = 0.5) -> set[int]:
    t: set[int] = set()
    for j in range(1, n):
        if sum(vals[k, i, j] for i in range(n)) > tol:
            t.add(j)
    return t


def _subtour_from(start: int, succ: dict[int, int]) -> list[int] | None:
    """Follow succ from start until a repeat; return nodes of directed cycle (excluding closing)."""
    seen: dict[int, int] = {}
    order: list[int] = []
    cur = start
    step = 0
    while cur in succ:
        if cur in seen:
            idx = seen[cur]
            return order[idx:]
        seen[cur] = len(order)
        order.append(cur)
        cur = succ[cur]
        step += 1
        if step > len(succ) + 5:
            break
    return None


def _find_subtour_cut(
    vals: np.ndarray, k: int, n: int
) -> list[int] | None:
    """
    If vehicle k's solution has a directed cycle on V+ not containing depot in the tour from 0,
    return subset S ⊂ V+ for SEC. Otherwise None.
    """
    succ = _extract_succ(vals, k, n)
    tk = _customers_served_by_vehicle(vals, k, n)
    if not tk:
        return None
    # Reachable from depot
    reachable: set[int] = set()
    stack = [0]
    while stack:
        u = stack.pop()
        if u in reachable:
            continue
        reachable.add(u)
        v = succ.get(u)
        if v is not None and v not in reachable:
            stack.append(v)
    if not tk.issubset(reachable):
        v0 = next(iter(tk - reachable))
        cyc = _subtour_from(v0, succ)
        if cyc is None or len(cyc) == 1:
            pair = _two_customer_cycle(vals, k, v0, n)
            if pair:
                return pair
        if cyc is None:
            cyc = [v0]
        s = [x for x in cyc if x != 0]
        if not s:
            s = [v0]
        if len(s) >= 2:
            return sorted(set(s))
        pair = _two_customer_cycle(vals, k, v0, n)
        return pair if pair else None
    # All served customers reachable; verify single return to depot
    path: list[int] = []
    cur = 0
    visited_edges = 0
    while cur in succ and visited_edges <= n + 2:
        nxt = succ[cur]
        path.append((cur, nxt))
        cur = nxt
        visited_edges += 1
        if cur == 0:
            break
    if cur != 0:
        return None
    cust_on_path = {j for (_, j) in path if j != 0}
    if cust_on_path != tk:
        leftover = tk - cust_on_path
        if leftover:
            v0 = next(iter(leftover))
            cyc = _subtour_from(v0, succ)
            if cyc and len(cyc) >= 2:
                return sorted(set(x for x in cyc if x != 0))
            pair = _two_customer_cycle(vals, k, v0, n)
            if pair:
                return pair
    return None


def solve_vrpcc_mip(
    inst: VRPCCInstance,
    time_limit_sec: float = 600.0,
    mip_gap: float = 1e-4,
    verbose: bool = False,
) -> MIPResult:
    n = inst.n_nodes
    m = inst.m
    d = inst.dist
    u = inst.u

    model = gp.Model("VRPCC")
    model.Params.OutputFlag = 1 if verbose else 0
    model.Params.TimeLimit = float(time_limit_sec)
    model.Params.MIPGap = float(mip_gap)
    model.Params.LazyConstraints = 1

    tau = model.addVar(vtype=GRB.CONTINUOUS, lb=0.0, name="tau")
    x = model.addVars(
        range(m),
        range(n),
        range(n),
        vtype=GRB.BINARY,
        name="x",
    )

    # (6) compatibility + fix impossible arcs
    for kk in range(m):
        for ii in range(n):
            for jj in range(n):
                if jj >= 1 and u[kk, jj] == 0:
                    x[kk, ii, jj].UB = 0.0
                # forbid customer self-loops x[k,j,j] (otherwise tau=0 "fake" visits)
                if ii == jj >= 1:
                    x[kk, ii, jj].UB = 0.0

    model.setObjective(tau, GRB.MINIMIZE)

    # (2)
    for kk in range(m):
        model.addConstr(
            gp.quicksum(d[i, j] * x[kk, i, j] for i in range(n) for j in range(n)) <= tau,
            name=f"span_{kk}",
        )

    # (3) each vehicle leaves depot once
    for kk in range(m):
        model.addConstr(gp.quicksum(x[kk, 0, j] for j in range(n)) == 1, name=f"leave_{kk}")

    # (4) flow
    for kk in range(m):
        for v in range(n):
            model.addConstr(
                gp.quicksum(x[kk, i, v] for i in range(n))
                == gp.quicksum(x[kk, v, j] for j in range(n)),
                name=f"flow_{kk}_{v}",
            )

    # (5) each customer visited exactly once
    for j in range(1, n):
        model.addConstr(
            gp.quicksum(x[kk, i, j] for kk in range(m) for i in range(n)) == 1,
            name=f"visit_{j}",
        )

    xarr = np.zeros((m, n, n))

    def _callback(model_cb: gp.Model, where: int) -> None:
        if where != GRB.Callback.MIPSOL:
            return
        for kk in range(m):
            for i in range(n):
                for j in range(n):
                    xarr[kk, i, j] = model_cb.cbGetSolution(x[kk, i, j])
        for kk in range(m):
            cut = _find_subtour_cut(xarr, kk, n)
            if cut and len(cut) >= 2:
                model_cb.cbLazy(
                    gp.quicksum(x[kk, i, j] for i in cut for j in cut) <= len(cut) - 1
                )

    t_wall0 = time.perf_counter()
    seen_cuts: set[tuple[int, frozenset[int]]] = set()
    max_sec_rounds = 200
    for _round in range(max_sec_rounds):
        model.optimize(_callback)
        if model.SolCount == 0:
            break
        for kk in range(m):
            for i in range(n):
                for j in range(n):
                    xarr[kk, i, j] = x[kk, i, j].X
        added = False
        for kk in range(m):
            cut = _find_subtour_cut(xarr, kk, n)
            if cut and len(cut) >= 2:
                key = (kk, frozenset(cut))
                if key in seen_cuts:
                    continue
                seen_cuts.add(key)
                model.addConstr(
                    gp.quicksum(x[kk, i, j] for i in cut for j in cut) <= len(cut) - 1,
                    name=f"sec_iter_{_round}_k{kk}",
                )
                added = True
        if not added:
            break
        model.update()

    elapsed = time.perf_counter() - t_wall0

    status = model.Status
    status_str = {
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.INF_OR_UNBD: "INF_OR_UNBD",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.TIME_LIMIT: "TIME_LIMIT",
    }.get(status, str(status))

    obj = float(model.ObjVal) if model.SolCount > 0 else None
    bound = float(model.ObjBound) if model.Status != GRB.INF_OR_UNBD else None
    gap = float(model.MIPGap) if model.IsMIP and model.SolCount > 0 else None

    routes: list[list[int]] | None = None
    if model.SolCount > 0:
        routes = []
        for kk in range(m):
            succ: dict[int, int] = {}
            for i in range(n):
                for j in range(n):
                    if x[kk, i, j].X > 0.5:
                        succ[i] = j
            tour = [0]
            cur = 0
            for _ in range(n + 3):
                if cur not in succ:
                    break
                cur = succ[cur]
                tour.append(cur)
                if cur == 0:
                    break
            routes.append(tour)

    return MIPResult(
        status=status_str,
        obj=obj,
        bound=bound,
        time_sec=elapsed,
        routes=routes,
        mip_gap=gap,
    )
