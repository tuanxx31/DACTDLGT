"""
Mục 4 bài báo: 2-opt theo đoạn depot + relocation sau Algorithm 2.

`scripts/run_comparison.py` gọi module này mặc định; `--no-local-search` để chỉ chạy tới mục 3.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vrpcc.instance import VRPCCInstance


def _split_segments(route: list[int]) -> list[list[int]]:
    """
    Tách một chuỗi tuyến của một xe (có thể ghép nhiều chuyến qua depot 0) thành các đoạn [0,...,0].

    Tham số:
        route: danh sách đỉnh, các lần quay về 0 đánh dấu ranh giới chuyến.

    Trả về: list các đoạn, mỗi đoạn kết thúc bằng 0 (và bắt đầu bằng 0 trừ đoạn đầu tiên có thể nối tiếp).
    """
    if not route:
        return [[0, 0]]
    segs: list[list[int]] = []
    cur: list[int] = []
    for node in route:
        cur.append(node)
        if node == 0 and len(cur) > 1:
            segs.append(cur)
            cur = [0]
    if len(cur) > 1:
        segs.append(cur)
    return segs if segs else [[0, 0]]


def _merge_segments(segs: list[list[int]]) -> list[int]:
    """
    Ghép lại các đoạn depot-khép kín thành một route dài một xe (bỏ depot trùng ở chỗ nối).

    Tham số:
        segs: output kiểu `_split_segments`.

    Trả về: một list đỉnh duy nhất.
    """
    if not segs:
        return [0, 0]
    out = segs[0][:]
    for s in segs[1:]:
        if out and s and out[-1] == 0 and s[0] == 0:
            out = out[:-1] + s
        else:
            out.extend(s)
    return out


def _two_opt_segment(inst: VRPCCInstance, vehicle: int, seg: list[int]) -> list[int]:
    """
    2-opt trên một đoạn tuyến đơn của một xe, dùng `inst.tour_length` (có kiểm tra u).

    Tham số:
        inst: instance.
        vehicle: chỉ số xe (ràng buộc tương thích).
        seg: đoạn dạng [0, khách..., 0].

    Trả về: đoạn sau khi cải thiện chi phí nếu có.
    """
    if len(seg) < 5:
        return seg
    inner = seg[1:-1]
    n = len(inner)
    best_c = inst.tour_length([0] + inner + [0], vehicle)
    improved = True
    while improved:
        improved = False
        for i in range(n):
            for j in range(i + 1, n):
                cand_inner = inner[:i] + list(reversed(inner[i : j + 1])) + inner[j + 1 :]
                cand = [0] + cand_inner + [0]
                c = inst.tour_length(cand, vehicle)
                if c + 1e-9 < best_c:
                    best_c = c
                    inner = cand_inner
                    improved = True
                    break
            if improved:
                break
    return [0] + inner + [0]


def _remove_customer(route: list[int], cust: int) -> list[int]:
    """
    Xoá một khách khỏi tuyến và dọn depot thừa (hai 0 liên tiếp), đảm bảo tuyến vẫn bắt đầu/kết thúc bằng 0 nếu có thể.

    Tham số:
        route: chuỗi đỉnh.
        cust: chỉ số khách cần bỏ.

    Trả về: tuyến mới (có thể [0,0] nếu rỗng).
    """
    r = [x for x in route if x != cust]
    out: list[int] = []
    for x in r:
        if x == 0 and out and out[-1] == 0:
            continue
        out.append(x)
    if not out:
        return [0, 0]
    if out[0] != 0:
        out.insert(0, 0)
    if out[-1] != 0:
        out.append(0)
    return out


def _best_insertion(inst: VRPCCInstance, veh: int, route: list[int], cust: int) -> list[int] | None:
    """
    Thử mọi vị trí chèn `cust` vào tuyến (bỏ qua depot), chỉ giữ cấu hình thỏa u[veh,cust] và chưa trùng khách.

    Tham số:
        inst: instance.
        veh: xe đích.
        route: tuyến hiện tại của xe đích (có 0 hai đầu).
        cust: khách cần chèn.

    Trả về: tuyến [0,...] tốt nhất theo chi phí, hoặc None nếu không chèn được.
    """
    nodes = [x for x in route if x != 0]
    if cust in nodes or inst.u[veh, cust] == 0:
        return None
    best: list[int] | None = None
    best_c = float("inf")
    for pos in range(len(nodes) + 1):
        new_nodes = nodes[:pos] + [cust] + nodes[pos:]
        cand = [0] + new_nodes + [0]
        c = inst.tour_length(cand, veh)
        if c < best_c:
            best_c = c
            best = cand
    return best


def _makespan(inst: VRPCCInstance, routes: list[list[int]]) -> float:
    """
    Makespan toàn fleet: max_k chi phí tuyến của xe k.

    Tham số:
        inst: instance (inst.m xe).
        routes: list độ dài m, mỗi phần tử là tuyến xe k.

    Trả về: giá trị float (mục tiêu local search cố giảm).
    """
    return max(inst.tour_length(routes[k], k) for k in range(inst.m))


def local_search(
    inst: VRPCCInstance,
    routes: list[list[int]],
    *,
    max_passes: int = 30,
) -> list[list[int]]:
    """
    Mục 4 bài báo (đơn giản hoá trong code): lặp tối đa `max_passes` vòng —
    (1) 2-opt từng đoạn depot-trên mỗi xe;
    (2) relocation: lấy khách trên xe có tuyến dài nhất, thử chuyển sang xe khác nếu giảm makespan.

    Tham số:
        inst: VRPCC.
        routes: lời giải khởi tạo từ Algorithm 2 (list tuyến theo xe).
        max_passes: giới hạn vòng lặp để tránh chạy quá lâu.

    Trả về: tuyến sau local search (bản sao, không sửa input gốc).
    """
    routes = copy.deepcopy(routes)
    m = inst.m
    for _ in range(max_passes):
        for k in range(m):
            segs = _split_segments(routes[k])
            routes[k] = _merge_segments([_two_opt_segment(inst, k, s) for s in segs])

        ms0 = _makespan(inst, routes)
        k_long = max(range(m), key=lambda i: inst.tour_length(routes[i], i))
        customers = [x for x in routes[k_long] if x != 0]
        if not customers:
            break
        best_ms = ms0
        best_routes = routes
        for cust in customers:
            for other in range(m):
                if other == k_long:
                    continue
                if inst.u[other, cust] == 0:
                    continue
                trial = copy.deepcopy(routes)
                trial[k_long] = _remove_customer(trial[k_long], cust)
                ins = _best_insertion(inst, other, trial[other], cust)
                if ins is None:
                    continue
                trial[other] = ins
                ms = _makespan(inst, trial)
                if ms + 1e-9 < best_ms:
                    best_ms = ms
                    best_routes = trial
        if best_ms + 1e-9 < ms0:
            routes = best_routes
        else:
            break
    return routes
