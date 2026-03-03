#!/usr/bin/env python3
"""
Giao diện web cho VRPCC (không dùng Tkinter).
Mục tiêu: người mới vẫn dùng được ngay với JSON dễ hiểu bằng tiếng Việt.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from typing import Any
import webbrowser

from vrpcc_core import (
    VRPCCInstance,
    build_demo_instance,
    euclidean_distance_matrix,
    format_solution,
    instance_from_json_str,
    instance_to_json_dict,
    solve_vrpcc_approx,
)


def _fallback_points(n_nodes: int) -> list[list[float]]:
    if n_nodes <= 1:
        return [[0.0, 0.0]]
    points = [[0.0, 0.0]]
    radius = 10.0
    for i in range(1, n_nodes):
        angle = (2.0 * math.pi * (i - 1)) / (n_nodes - 1)
        points.append([radius * math.cos(angle), radius * math.sin(angle)])
    return points


def _pick_field(data: dict[str, Any], keys: list[str], *, required: bool = True, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    if required:
        raise ValueError(f"Thiếu trường bắt buộc, cần một trong: {keys}")
    return default


def _default_labels(instance: VRPCCInstance) -> tuple[dict[int, str], dict[int, str]]:
    node_labels: dict[int, str] = {0: "Kho"}
    for node in sorted(instance.customers):
        node_labels[node] = f"Khách {node}"
    vehicle_labels: dict[int, str] = {}
    for vehicle in instance.vehicles:
        vehicle_labels[vehicle] = f"Xe {vehicle}"
    return node_labels, vehicle_labels


def build_demo_human_json() -> dict[str, Any]:
    """
    JSON mẫu theo kiểu gần ngôn ngữ tự nhiên để người mới dễ đọc/sửa.
    """
    demo = build_demo_instance()
    points = demo.points or _fallback_points(len(demo.dist))
    customer_names = {
        1: "Nhà cô Lan",
        2: "Nhà chú Minh",
        3: "Chung cư Hoa Sen",
        4: "Cửa hàng An Phát",
        5: "Nhà bác Hùng",
        6: "Nhà chị Mai",
        7: "Nhà anh Tuấn",
        8: "Phòng khám Bình An",
    }
    vehicle_profiles = {
        0: {"tên": "Xe A", "tay_nghề": "Chăm sóc vết thương"},
        1: {"tên": "Xe B", "tay_nghề": "Vật lý trị liệu"},
        2: {"tên": "Xe C", "tay_nghề": "Tiêm thuốc tại nhà"},
    }
    required_skills_by_node = {
        1: ["Chăm sóc vết thương", "Tiêm thuốc tại nhà"],
        2: ["Chăm sóc vết thương"],
        3: ["Chăm sóc vết thương", "Vật lý trị liệu"],
        4: ["Chăm sóc vết thương", "Vật lý trị liệu"],
        5: ["Vật lý trị liệu", "Tiêm thuốc tại nhà"],
        6: ["Vật lý trị liệu", "Tiêm thuốc tại nhà"],
        7: ["Tiêm thuốc tại nhà"],
        8: ["Chăm sóc vết thương", "Tiêm thuốc tại nhà"],
    }

    customers: list[dict[str, Any]] = []
    for node in sorted(demo.customers):
        x, y = points[node]
        allowed = [v for v in demo.vehicles if node in demo.compatible[v]]
        customers.append(
            {
                "id": node,
                "tên": customer_names.get(node, f"Khách {node}"),
                "x": x,
                "y": y,
                "tay_nghề_cần": required_skills_by_node.get(node, []),
                "xe_phù_hợp": allowed,
            }
        )

    vehicles = []
    for v in demo.vehicles:
        profile = vehicle_profiles.get(v, {"tên": f"Xe {v}", "tay_nghề": "Chưa khai báo"})
        vehicles.append({"id": v, "tên": profile["tên"], "tay_nghề": profile["tay_nghề"]})

    return {
        "mô_tả": "Ví dụ trực quan: điều phối 3 xe phục vụ 8 khách hàng",
        "điểm_xuất_phát": {
            "tên": "Kho trung tâm",
            "x": points[0][0],
            "y": points[0][1],
        },
        "xe": vehicles,
        "khách_hàng": customers,
    }


def parse_human_json(raw: str) -> tuple[VRPCCInstance, dict[int, str], dict[int, str]]:
    """
    Parse JSON "dễ hiểu":
    - điểm_xuất_phát
    - xe
    - khách_hàng với xe_phù_hợp
    """
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON phải là object ở mức cao nhất.")

    if "khách_hàng" not in data and "khach_hang" not in data:
        raise ValueError("Không thấy trường 'khách_hàng' (hoặc 'khach_hang').")

    depot = _pick_field(data, ["điểm_xuất_phát", "diem_xuat_phat", "depot"])
    vehicles_data = _pick_field(data, ["xe", "vehicles"])
    customers_data = _pick_field(data, ["khách_hàng", "khach_hang", "customers"])

    if not isinstance(depot, dict):
        raise ValueError("Trường 'điểm_xuất_phát' phải là object.")
    if not isinstance(vehicles_data, list) or len(vehicles_data) == 0:
        raise ValueError("Trường 'xe' phải là danh sách và không được rỗng.")
    if not isinstance(customers_data, list) or len(customers_data) == 0:
        raise ValueError("Trường 'khách_hàng' phải là danh sách và không được rỗng.")

    depot_name = str(_pick_field(depot, ["tên", "ten", "name"], required=False, default="Kho"))
    depot_x = float(_pick_field(depot, ["x"]))
    depot_y = float(_pick_field(depot, ["y"]))
    points: list[tuple[float, float]] = [(depot_x, depot_y)]

    ext_vehicle_to_internal: dict[int, int] = {}
    vehicle_labels: dict[int, str] = {}
    vehicle_skills: dict[int, str] = {}
    for idx, item in enumerate(vehicles_data):
        if isinstance(item, dict):
            ext_id = int(_pick_field(item, ["id"], required=False, default=idx))
            vname = str(_pick_field(item, ["tên", "ten", "name"], required=False, default=f"Xe {ext_id}"))
            vskill = _pick_field(
                item,
                ["tay_nghề", "tay_nghe", "kỹ_năng", "ky_nang", "skill"],
                required=False,
                default=None,
            )
            if vskill is not None:
                vskill = str(vskill)
        else:
            ext_id = int(item)
            vname = f"Xe {ext_id}"
            vskill = None

        if ext_id in ext_vehicle_to_internal:
            raise ValueError(f"ID xe bị trùng: {ext_id}")

        internal = len(ext_vehicle_to_internal)
        ext_vehicle_to_internal[ext_id] = internal
        if vskill:
            vehicle_skills[internal] = vskill
            vehicle_labels[internal] = f"{vname} - {vskill}"
        else:
            vehicle_labels[internal] = vname

    compatible: list[set[int]] = [set() for _ in range(len(ext_vehicle_to_internal))]
    node_labels: dict[int, str] = {0: depot_name}
    seen_customer_ids: set[int] = set()

    for idx, customer in enumerate(customers_data, start=1):
        if not isinstance(customer, dict):
            raise ValueError("Mỗi phần tử trong 'khách_hàng' phải là object.")

        ext_customer_id = int(_pick_field(customer, ["id"], required=False, default=idx))
        if ext_customer_id in seen_customer_ids:
            raise ValueError(f"ID khách hàng bị trùng: {ext_customer_id}")
        seen_customer_ids.add(ext_customer_id)

        cname = str(
            _pick_field(
                customer,
                ["tên", "ten", "name"],
                required=False,
                default=f"Khách {ext_customer_id}",
            )
        )
        cx = float(_pick_field(customer, ["x"]))
        cy = float(_pick_field(customer, ["y"]))
        node_id = len(points)  # node 0 là depot, khách bắt đầu từ 1
        points.append((cx, cy))

        allowed = _pick_field(
            customer,
            ["xe_phù_hợp", "xe_phu_hop", "duoc_xe", "xe", "vehicles"],
        )
        if not isinstance(allowed, list) or len(allowed) == 0:
            raise ValueError(
                f"Khách hàng '{cname}' phải có danh sách xe phù hợp "
                f"trong trường 'xe_phù_hợp'."
            )

        for ext_vehicle in allowed:
            ext_vehicle_id = int(ext_vehicle)
            if ext_vehicle_id not in ext_vehicle_to_internal:
                raise ValueError(
                    f"Khách hàng '{cname}' tham chiếu xe {ext_vehicle_id} "
                    f"nhưng xe này không có trong danh sách 'xe'."
                )
            internal_vehicle = ext_vehicle_to_internal[ext_vehicle_id]
            compatible[internal_vehicle].add(node_id)

        required_skill_value = _pick_field(
            customer,
            ["tay_nghề_cần", "tay_nghe_can", "kỹ_năng_cần", "ky_nang_can", "skill_required"],
            required=False,
            default=None,
        )
        required_skills: list[str] = []
        if required_skill_value is None:
            # Nếu người dùng không khai báo, tự suy ra từ tay nghề các xe phù hợp.
            derived: list[str] = []
            for ext_vehicle in allowed:
                ext_vehicle_id = int(ext_vehicle)
                internal_vehicle = ext_vehicle_to_internal[ext_vehicle_id]
                if internal_vehicle in vehicle_skills:
                    derived.append(vehicle_skills[internal_vehicle])
            required_skills = sorted(set(derived))
        elif isinstance(required_skill_value, list):
            required_skills = [str(x) for x in required_skill_value if str(x).strip()]
        else:
            required_skills = [str(required_skill_value)]

        if required_skills:
            req_text = ", ".join(required_skills)
            node_labels[node_id] = f"{cname} (cần: {req_text})"
        else:
            node_labels[node_id] = cname

    instance = VRPCCInstance(
        dist=euclidean_distance_matrix(points),
        compatible=compatible,
        points=[(x, y) for x, y in points],
    )
    instance.validate()
    return instance, node_labels, vehicle_labels


def parse_any_instance_json(raw: str) -> tuple[VRPCCInstance, dict[int, str], dict[int, str], str]:
    """
    Ưu tiên đọc dạng dễ hiểu, sau đó fallback sang dạng kỹ thuật.
    """
    human_error: Exception | None = None
    try:
        instance, node_labels, vehicle_labels = parse_human_json(raw)
        return instance, node_labels, vehicle_labels, "dễ hiểu"
    except Exception as exc:  # noqa: BLE001
        human_error = exc

    technical_error: Exception | None = None
    try:
        instance = instance_from_json_str(raw)
        node_labels, vehicle_labels = _default_labels(instance)
        return instance, node_labels, vehicle_labels, "kỹ thuật"
    except Exception as exc:  # noqa: BLE001
        technical_error = exc

    raise ValueError(
        "Không đọc được JSON.\n"
        f"- Lỗi dạng dễ hiểu: {human_error}\n"
        f"- Lỗi dạng kỹ thuật: {technical_error}"
    )


HTML_PAGE = r"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>VRPCC - Giao diện trực quan</title>
  <style>
    :root {
      --nền: #f7fafc;
      --thẻ: #ffffff;
      --chữ: #1f2937;
      --mờ: #6b7280;
      --viền: #d1d5db;
      --chính: #0f766e;
      --chính-đậm: #134e4a;
    }
    body {
      margin: 0;
      font-family: "Segoe UI", "SF Pro Text", Helvetica, Arial, sans-serif;
      color: var(--chữ);
      background: radial-gradient(circle at 0% 0%, #dff7f2 0%, #f5f8fc 50%, #eef3fb 100%);
    }
    .khung {
      width: calc(100vw - 28px);
      max-width: 1900px;
      margin: 0 auto;
      padding: 14px;
      box-sizing: border-box;
    }
    .thanh-tren {
      background: var(--thẻ);
      border: 1px solid var(--viền);
      border-radius: 14px;
      padding: 14px;
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }
    .thanh-tren label {
      font-size: 14px;
      color: var(--mờ);
    }
    .thanh-tren input {
      width: 95px;
      padding: 6px 8px;
      border: 1px solid var(--viền);
      border-radius: 8px;
      font-size: 14px;
    }
    .công-tắc-ls {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 14px;
      color: var(--chữ);
      padding: 4px 8px;
      border: 1px solid var(--viền);
      border-radius: 8px;
      background: #f9fbff;
    }
    .công-tắc-ls input[type="checkbox"] {
      width: 16px;
      height: 16px;
    }
    button {
      border: 0;
      border-radius: 10px;
      padding: 9px 13px;
      font-size: 14px;
      cursor: pointer;
      background: var(--chính-đậm);
      color: white;
    }
    button.phụ {
      background: #4b5563;
    }
    button.sáng {
      background: #0f766e;
    }
    #status {
      font-size: 13px;
      color: #0f172a;
      min-height: 18px;
    }
    .lưới {
      display: grid;
      grid-template-columns: minmax(340px, 0.75fr) minmax(860px, 1.45fr);
      gap: 12px;
      margin-top: 12px;
      align-items: start;
    }
    .lưới > .thẻ {
      min-width: 0;
    }
    .thẻ {
      background: var(--thẻ);
      border: 1px solid var(--viền);
      border-radius: 14px;
      padding: 12px;
    }
    h2 {
      margin: 0 0 8px;
      font-size: 18px;
    }
    h3 {
      margin: 0 0 8px;
      font-size: 15px;
    }
    .hướng-dẫn {
      margin: 0 0 10px;
      padding: 10px 12px;
      background: #ecfdf5;
      border: 1px solid #a7f3d0;
      border-radius: 10px;
      font-size: 14px;
      line-height: 1.45;
    }
    textarea {
      width: 100%;
      min-height: 560px;
      resize: vertical;
      box-sizing: border-box;
      border: 1px solid var(--viền);
      border-radius: 8px;
      padding: 10px;
      font-family: Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      white-space: pre;
    }
    .vùng-đồ-thị {
      border: 1px solid var(--viền);
      border-radius: 8px;
      background: #fff;
      overflow: auto;
      max-height: 680px;
      min-height: 500px;
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
    }
    canvas {
      display: block;
      background: #fff;
      width: auto;
      height: auto;
    }
    #legend {
      margin-top: 8px;
      font-size: 13px;
      color: var(--mờ);
    }
    #out {
      margin-top: 8px;
      min-height: 210px;
      max-height: 300px;
      overflow: auto;
      border: 1px solid var(--viền);
      border-radius: 8px;
      padding: 10px;
      background: #f9fbff;
      font-family: Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      white-space: pre-wrap;
    }
    @media (max-width: 1050px) {
      .lưới {
        grid-template-columns: 1fr;
      }
      textarea {
        min-height: 340px;
      }
    }
  </style>
</head>
<body>
  <div class="khung">
    <div class="thanh-tren">
      <label>epsilon:
        <input id="eps" type="number" step="0.001" value="0.01" />
      </label>
      <label>beta:
        <input id="beta" type="number" step="0.1" value="1.0" />
      </label>
      <label class="công-tắc-ls" title="Bật/tắt hậu xử lý thực nghiệm theo paper">
        <input id="applyLocalSearch" type="checkbox" checked />
        Hậu xử lý (2-opt + relocation)
      </label>
      <button class="sáng" onclick="napMauDeHieu()">Nạp mẫu dễ hiểu</button>
      <button class="phụ" onclick="napMauKyThuat()">Nạp mẫu kỹ thuật</button>
      <button onclick="giaiBaiToan()">Giải bài toán</button>
      <span id="status"></span>
    </div>

    <div class="lưới">
      <div class="thẻ">
        <h2>Dữ liệu đầu vào</h2>
        <div class="hướng-dẫn">
          <strong>Cách demo nhanh cho người mới:</strong><br />
          Bước 1: Bấm <em>Nạp mẫu dễ hiểu</em>.<br />
          Bước 2: Bấm <em>Giải bài toán</em>.<br />
          Bước 3: Xem tuyến trên hình và đọc nhật ký kết quả.<br />
          Khung minh họa có thể cuộn ngang/dọc để xem đầy đủ nhãn dài.<br />
          Bạn có thể chỉnh nhanh tọa độ <code>x, y</code>, <code>tay_nghề_cần</code>
          hoặc danh sách <code>xe_phù_hợp</code>.
        </div>
        <h3>JSON (dạng dễ hiểu hoặc kỹ thuật)</h3>
        <textarea id="inputJson"></textarea>
      </div>

      <div class="thẻ">
        <h2>Minh họa tuyến đường</h2>
        <div class="vùng-đồ-thị">
          <canvas id="plot" width="980" height="620"></canvas>
        </div>
        <div id="legend"></div>
        <h3 style="margin-top:12px;">Kết quả / Nhật ký</h3>
        <div id="out"></div>
      </div>
    </div>
  </div>

  <script>
    const colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#17becf"];
    let demoCache = null;

    function setStatus(text) {
      document.getElementById("status").textContent = text;
    }

    async function lấyDemo() {
      if (demoCache) return demoCache;
      const resp = await fetch("/api/demo");
      demoCache = await resp.json();
      return demoCache;
    }

    async function napMauDeHieu() {
      setStatus("Đang tải mẫu dễ hiểu...");
      const data = await lấyDemo();
      document.getElementById("inputJson").value = JSON.stringify(data.instance_human, null, 2);
      document.getElementById("out").textContent =
        "Đã nạp mẫu dễ hiểu.\n" +
        "Bạn có thể bấm 'Giải bài toán' ngay, hoặc sửa thử tọa độ/tay_nghề_cần/xe_phù_hợp để xem kết quả thay đổi.";
      drawPlot(data.plot.points, {}, data.plot.node_labels, data.plot.vehicle_labels);
      setStatus("Sẵn sàng");
    }

    async function napMauKyThuat() {
      setStatus("Đang tải mẫu kỹ thuật...");
      const data = await lấyDemo();
      document.getElementById("inputJson").value = JSON.stringify(data.instance_technical, null, 2);
      document.getElementById("out").textContent =
        "Đã nạp mẫu kỹ thuật (dist + compatible).\n" +
        "Dạng này phù hợp khi bạn muốn tích hợp trực tiếp với mã lõi.";
      drawPlot(data.plot.points, {}, data.plot.node_labels, data.plot.vehicle_labels);
      setStatus("Sẵn sàng");
    }

    function estimateCanvasSize(points, nodeLabels) {
      const n = points.length;
      const width = Math.min(
        1800,
        930 + Math.max(0, n - 8) * 36
      );
      const height = Math.min(
        1300,
        610 + Math.max(0, n - 8) * 30
      );
      return { width, height };
    }

    function normalizePoints(points, width, height) {
      const margin = 58;
      const xs = points.map(p => p[0]);
      const ys = points.map(p => p[1]);
      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      const spanX = Math.max(maxX - minX, 1e-9);
      const spanY = Math.max(maxY - minY, 1e-9);
      const out = {};
      points.forEach((p, idx) => {
        const nx = margin + ((p[0] - minX) / spanX) * (width - 2 * margin);
        const ny = margin + ((maxY - p[1]) / spanY) * (height - 2 * margin);
        out[idx] = [nx, ny];
      });
      return out;
    }

    function catDoan(text, maxLen) {
      if (!text) return "";
      if (text.length <= maxLen) return text;
      return text.slice(0, maxLen) + "…";
    }

    function tachDongTheoKyNang(text, maxLen) {
      const rawParts = (text || "")
        .split(",")
        .map(s => s.trim())
        .filter(Boolean);
      if (rawParts.length === 0) return [];

      const lines = [];
      let current = "";
      rawParts.forEach(part => {
        const piece = catDoan(part, Math.max(12, maxLen - 2));
        if (!current) {
          current = piece;
          return;
        }
        const candidate = `${current}, ${piece}`;
        if (candidate.length <= maxLen) {
          current = candidate;
        } else {
          lines.push(current);
          current = piece;
        }
      });
      if (current) lines.push(current);
      return lines;
    }

    function taoNhanNhieuDong(node, rawName) {
      const fallback = node === 0 ? "Kho" : `Khách ${node}`;
      const text = (rawName || fallback).trim();
      const match = text.match(/^(.*)\s*\(cần:\s*(.*)\)\s*$/u);

      const title = catDoan(match ? match[1].trim() : text, 34);
      const lines = [`${node}: ${title}`];

      if (match && match[2]) {
        const reqLines = tachDongTheoKyNang(match[2].trim(), 34);
        reqLines.forEach((line, idx) => {
          lines.push(idx === 0 ? `cần: ${line}` : `     ${line}`);
        });
      }
      return lines;
    }

    function drawPlot(points, routesByVehicle, nodeLabels = {}, vehicleLabels = {}) {
      const canvas = document.getElementById("plot");
      const ctx = canvas.getContext("2d");
      const size = estimateCanvasSize(points, nodeLabels);
      canvas.width = size.width;
      canvas.height = size.height;
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const coords = normalizePoints(points, w, h);

      Object.keys(routesByVehicle || {}).forEach(v => {
        const vehicleId = Number(v);
        const routeList = routesByVehicle[v] || [];
        routeList.forEach((route, idx) => {
          if (!route || route.length === 0) return;
          const path = [0, ...route, 0];
          ctx.beginPath();
          path.forEach((node, i) => {
            const [x, y] = coords[node];
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.strokeStyle = colors[vehicleId % colors.length];
          ctx.lineWidth = 2;
          ctx.setLineDash(idx > 0 ? [6, 3] : []);
          ctx.stroke();
        });
      });
      ctx.setLineDash([]);

      Object.keys(coords).forEach(nodeStr => {
        const node = Number(nodeStr);
        const [x, y] = coords[node];
        const r = node === 0 ? 6 : 4;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, 2 * Math.PI);
        ctx.fillStyle = node === 0 ? "#d62728" : "#111111";
        ctx.fill();

        const rawName = nodeLabels[node] || (node === 0 ? "Kho" : `Khách ${node}`);
        const lines = taoNhanNhieuDong(node, rawName);
        ctx.fillStyle = "#111111";
        ctx.font = "11px Menlo, monospace";
        const lineHeight = 14;
        const textWidth = Math.max(...lines.map(line => ctx.measureText(line).width));
        const boxHeight = lineHeight * lines.length + 2;
        let tx = x + 10;
        let ty = y - 8;
        if (tx + textWidth > w - 8) tx = x - textWidth - 12;
        if (tx < 8) tx = 8;
        if (ty < 14) ty = y + 16;
        if (ty + boxHeight > h - 4) ty = h - boxHeight - 4;

        ctx.fillStyle = "rgba(255,255,255,0.85)";
        ctx.fillRect(tx - 3, ty - 12, textWidth + 6, boxHeight + 2);
        ctx.fillStyle = "#111111";
        lines.forEach((line, idx) => {
          ctx.fillText(line, tx, ty + idx * lineHeight);
        });
      });

      const legend = document.getElementById("legend");
      const vids = Object.keys(routesByVehicle || {}).map(Number).sort((a, b) => a - b);
      const shown = vids.length > 0 ? vids : Object.keys(vehicleLabels).map(Number).sort((a, b) => a - b);
      legend.innerHTML = shown.map(v => {
        const c = colors[v % colors.length];
        const name = vehicleLabels[v] || `Xe ${v}`;
        return `<span style="display:inline-flex;align-items:center;margin-right:12px;">
          <span style="width:16px;height:3px;background:${c};display:inline-block;margin-right:5px;"></span>
          ${name}
        </span>`;
      }).join("");
    }

    async function giaiBaiToan() {
      const eps = Number(document.getElementById("eps").value);
      const beta = Number(document.getElementById("beta").value);
      const applyLocalSearch = document.getElementById("applyLocalSearch").checked;
      const inputJson = document.getElementById("inputJson").value;
      setStatus("Đang giải...");

      const resp = await fetch("/api/solve", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ eps, beta, apply_local_search: applyLocalSearch, instance_json: inputJson })
      });
      const data = await resp.json();
      if (!data.ok) {
        document.getElementById("out").textContent = "Lỗi dữ liệu đầu vào:\n" + data.error;
        setStatus("Lỗi");
        return;
      }

      const lsText = data.apply_local_search ? "BẬT" : "TẮT";
      document.getElementById("out").textContent =
        `Đã đọc JSON theo dạng: ${data.parse_mode}\n` +
        `Hậu xử lý local search: ${lsText}\n\n` +
        data.output_text;
      drawPlot(
        data.plot.points,
        data.plot.routes_by_vehicle,
        data.plot.node_labels,
        data.plot.vehicle_labels
      );
      setStatus("Hoàn tất");
    }

    napMauDeHieu().catch(err => {
      document.getElementById("out").textContent = "Không tải được dữ liệu mẫu: " + err;
      setStatus("Lỗi");
    });
  </script>
</body>
</html>
"""


class VRPCCWebHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, html: str, status: int = 200) -> None:
        raw = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path.startswith("/?"):
            self._send_html(HTML_PAGE)
            return

        if self.path == "/api/demo":
            technical_instance = build_demo_instance()
            technical_json = instance_to_json_dict(technical_instance)
            human_json = build_demo_human_json()

            # Parse human demo to get labels/points exactly as solver will see.
            parsed_human, node_labels, vehicle_labels = parse_human_json(
                json.dumps(human_json, ensure_ascii=False)
            )
            points = parsed_human.points or _fallback_points(len(parsed_human.dist))

            self._send_json(
                {
                    "ok": True,
                    "instance_human": human_json,
                    "instance_technical": technical_json,
                    "plot": {
                        "points": points,
                        "node_labels": node_labels,
                        "vehicle_labels": vehicle_labels,
                    },
                }
            )
            return

        self._send_json({"ok": False, "error": "Không tìm thấy endpoint."}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/solve":
            self._send_json({"ok": False, "error": "Không tìm thấy endpoint."}, status=404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body)
            eps = float(payload["eps"])
            beta = float(payload["beta"])
            apply_local_search_raw = payload.get("apply_local_search", True)
            if isinstance(apply_local_search_raw, bool):
                apply_local_search = apply_local_search_raw
            elif isinstance(apply_local_search_raw, str):
                apply_local_search = apply_local_search_raw.strip().lower() in {"1", "true", "yes", "on"}
            else:
                apply_local_search = bool(apply_local_search_raw)
            instance_json = str(payload["instance_json"])

            instance, node_labels, vehicle_labels, parse_mode = parse_any_instance_json(instance_json)
            solution = solve_vrpcc_approx(
                instance,
                eps=eps,
                beta=beta,
                apply_local_search=apply_local_search,
            )
            points = instance.points or _fallback_points(len(instance.dist))

            self._send_json(
                {
                    "ok": True,
                    "parse_mode": parse_mode,
                    "apply_local_search": apply_local_search,
                    "output_text": format_solution(solution, instance),
                    "plot": {
                        "points": points,
                        "routes_by_vehicle": solution.tours_by_vehicle,
                        "node_labels": node_labels,
                        "vehicle_labels": vehicle_labels,
                    },
                }
            )
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "error": str(exc)}, status=400)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        # Giảm log để terminal gọn hơn.
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UI web cho VRPCC (tiếng Việt, dễ demo).")
    parser.add_argument("--host", default="127.0.0.1", help="Địa chỉ host.")
    parser.add_argument("--port", type=int, default=8765, help="Cổng chạy server.")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Không tự động mở trình duyệt.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), VRPCCWebHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"VRPCC web đang chạy tại: {url}")
    print("Nhấn Ctrl+C để dừng.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
