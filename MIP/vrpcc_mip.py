from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import gurobipy as gp
from gurobipy import GRB

from instancegen import Instance


@dataclass
class MIPReport:
    lb: float | None
    ub: float | None
    best_tau: float | None
    mip_gap: float | None
    time_sec: float  # wall-clock toàn bộ solve_vrpcc (dựng mô hình + optimize)
    gurobi_runtime: float  # chỉ lệnh optimize() — thuộc tính model.Runtime
    status: int
    nodes: int


def _status_name(code: int) -> str:
    names = {
        GRB.LOADED: "LOADED",
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.INF_OR_UNBD: "INF_OR_UNBD",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.CUTOFF: "CUTOFF",
        GRB.ITERATION_LIMIT: "ITERATION_LIMIT",
        GRB.NODE_LIMIT: "NODE_LIMIT",
        GRB.TIME_LIMIT: "TIME_LIMIT",
        GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
        GRB.INTERRUPTED: "INTERRUPTED",
        GRB.NUMERIC: "NUMERIC",
        GRB.SUBOPTIMAL: "SUBOPTIMAL",
        GRB.INPROGRESS: "INPROGRESS",
        GRB.USER_OBJ_LIMIT: "USER_OBJ_LIMIT",
    }
    return names.get(code, str(code))


def _fmt_float(x: float | None) -> str:
    if x is None:
        return "n/a"
    return repr(x)


def format_mip_summary(r: MIPReport) -> str:
    gap_s = f"{repr(100.0 * r.mip_gap)} %" if r.mip_gap is not None else "n/a"

    return "\n".join([
        f"  LB (ObjBound):         {_fmt_float(r.lb)}",
        f"  UB (tau.X):            {_fmt_float(r.ub)}",
        f"  B (budget, tau.X):     {_fmt_float(r.best_tau)}",
        f"  MIP gap (relative):    {gap_s}",
        f"  Time (wall, full):     {repr(r.time_sec)} s",
        f"  Time (Gurobi solve):   {repr(r.gurobi_runtime)} s",
        f"  Status:                {_status_name(r.status)} ({r.status})",
        f"  Nodes (B&B):           {r.nodes}",
    ])


def _feasible_arcs(inst: Instance) -> List[Tuple[int, int, int]]:
    n, m_veh = inst.n, inst.m
    u = inst.u
    arcs: List[Tuple[int, int, int]] = []

    for k in range(m_veh):
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if i > 0 and u[k][i] == 0:
                    continue
                if j > 0 and u[k][j] == 0:
                    continue
                arcs.append((k, i, j))

    return arcs


def _extract_customer_edges(
    m_veh: int,
    x_val: Dict[Tuple[int, int, int], float],
) -> Dict[int, List[Tuple[int, int]]]:
    edges_by_vehicle: Dict[int, List[Tuple[int, int]]] = {k: [] for k in range(m_veh)}
    for (k, i, j), val in x_val.items():
        if val > 0.5 and i > 0 and j > 0:
            edges_by_vehicle[k].append((i, j))
    return edges_by_vehicle


def _find_customer_subtours(
    m_veh: int,
    x_val: Dict[Tuple[int, int, int], float],
) -> List[Tuple[int, List[int]]]:
    edges_by_vehicle = _extract_customer_edges(m_veh, x_val)
    subtours: List[Tuple[int, List[int]]] = []

    for k in range(m_veh):
        succ: Dict[int, int] = {}
        for i, j in edges_by_vehicle[k]:
            succ[i] = j

        visited: Set[int] = set()

        for start in list(succ.keys()):
            if start in visited:
                continue

            path: List[int] = []
            pos: Dict[int, int] = {}
            cur = start

            while cur in succ and cur not in visited:
                if cur in pos:
                    cycle = path[pos[cur]:]
                    if len(cycle) >= 2:
                        subtours.append((k, sorted(set(cycle))))
                    break
                pos[cur] = len(path)
                path.append(cur)
                cur = succ[cur]

            for node in path:
                visited.add(node)

    unique: List[Tuple[int, List[int]]] = []
    seen: Set[Tuple[int, Tuple[int, ...]]] = set()
    for k, S in subtours:
        key = (k, tuple(S))
        if key not in seen:
            seen.add(key)
            unique.append((k, S))

    return unique


def solve_vrpcc(
    inst: Instance,
    time_limit: float = 600.0,
    mip_gap: float = 1e-4,
    verbose: bool = True,
) -> MIPReport:
    t_wall0 = time.perf_counter()
    n = inst.n
    m_veh = inst.m
    c = inst.c

    arcs = _feasible_arcs(inst)
    arc_set = set(arcs)

    model = gp.Model("VRPCC")
    model.Params.OutputFlag = 1 if verbose else 0
    model.Params.TimeLimit = time_limit
    model.Params.MIPGap = mip_gap
    model.Params.LazyConstraints = 1

    x = model.addVars(arcs, vtype=GRB.BINARY, name="x")
    tau = model.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="tau")
    model.setObjective(tau, GRB.MINIMIZE)

    # Makespan
    for k in range(m_veh):
        model.addConstr(
            gp.quicksum(c[i][j] * x[k, i, j] for (kk, i, j) in arcs if kk == k) <= tau,
            name=f"makespan_{k}",
        )

    # Mỗi xe dùng tối đa 1 route
    for k in range(m_veh):
        out_depot = gp.quicksum(x[k, 0, j] for j in range(1, n) if (k, 0, j) in arc_set)
        in_depot = gp.quicksum(x[k, i, 0] for i in range(1, n) if (k, i, 0) in arc_set)
        model.addConstr(out_depot <= 1, name=f"depot_out_le1_{k}")
        model.addConstr(in_depot <= 1, name=f"depot_in_le1_{k}")

    # Flow balance
    for k in range(m_veh):
        for v in range(n):
            inflow = gp.quicksum(
                x[k, i, v] for i in range(n) if i != v and (k, i, v) in arc_set
            )
            outflow = gp.quicksum(
                x[k, v, j] for j in range(n) if j != v and (k, v, j) in arc_set
            )
            model.addConstr(inflow == outflow, name=f"flow_{k}_{v}")

    # Mỗi khách được thăm đúng 1 lần
    for j in range(1, n):
        model.addConstr(
            gp.quicksum(
                x[k, i, j]
                for k in range(m_veh)
                for i in range(n)
                if i != j and (k, i, j) in arc_set
            ) == 1,
            name=f"visit_once_{j}",
        )

    def _callback(cb_model, where):
        if where != GRB.Callback.MIPSOL:
            return

        x_sol: Dict[Tuple[int, int, int], float] = {}
        for key in arcs:
            val = cb_model.cbGetSolution(x[key])
            if val > 0.5:
                x_sol[key] = val

        for k, S in _find_customer_subtours(m_veh, x_sol):
            lhs = gp.quicksum(
                x[k, i, j]
                for i in S
                for j in S
                if i != j and (k, i, j) in arc_set
            )
            cb_model.cbLazy(lhs <= len(S) - 1)

    model.optimize(_callback)

    gurobi_rt = model.Runtime
    wall_sec = time.perf_counter() - t_wall0

    try:
        lb = model.ObjBound
    except (gp.GurobiError, AttributeError, TypeError, ValueError):
        lb = None

    try:
        gap = model.MIPGap
    except (gp.GurobiError, AttributeError, TypeError, ValueError):
        gap = None

    try:
        nodes = int(model.NodeCount)
    except (gp.GurobiError, AttributeError, TypeError, ValueError):
        nodes = 0

    ub = None
    best_tau = None
    if model.SolCount > 0:
        try:
            # B (budget) va U (incumbent / UB): lay tu bien tau.X, khong dung ObjVal
            tx = tau.X
            ub = tx
            best_tau = tx
        except (gp.GurobiError, AttributeError, TypeError, ValueError):
            try:
                tx = tau.getAttr(GRB.Attr.X)
                ub = tx
                best_tau = tx
            except (gp.GurobiError, AttributeError, TypeError, ValueError):
                ub = None
                best_tau = None

    return MIPReport(
        lb=lb,
        ub=ub,
        best_tau=best_tau,
        mip_gap=gap,
        time_sec=wall_sec,
        gurobi_runtime=gurobi_rt,
        status=int(model.Status),
        nodes=nodes,
    )