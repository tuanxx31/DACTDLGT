# Ghi chú báo cáo mã nguồn VRPCC

Tài liệu này tóm tắt mã nguồn trong repo để dùng khi trình bày báo cáo về bài toán
**Vehicle Routing Problem with Compatibility Constraints (VRPCC)** và thuật toán xấp xỉ
theo bài báo *An Approximation Algorithm for Vehicle Routing with Compatibility Constraints*.

## 1. Mục tiêu chương trình

Chương trình hiện thực một pipeline giải VRPCC:

1. Đọc dữ liệu instance từ file JSON.
2. Chạy thuật toán xấp xỉ của bài báo:
   - Algorithm 2: binary search trên ngân sách `B`.
   - Algorithm 1: greedy MCG-VRP để phủ khách theo từng lượt.
   - Oracle k-TSP bicriteria với hệ số `beta = 5`.
3. Tùy chọn cải thiện nghiệm bằng local search:
   - 2-opt trên từng đoạn tuyến.
   - Relocation: chuyển khách giữa các xe nếu giảm makespan.
4. Ghi kết quả ra JSON, log và hình vẽ tuyến đường.

Mục tiêu tối ưu là **makespan**, tức chi phí tuyến lớn nhất trong toàn bộ đội xe:

```text
makespan = max_k cost(route_k)
```

## 2. Cấu trúc mã nguồn chính

| File | Vai trò |
|---|---|
| `run_selected_instances.py` | File chạy riêng theo danh sách instance cố định, không cần truyền tham số `--instance` trên terminal. |
| `app.py` | CLI chính để chạy thuật toán xấp xỉ, có hỗ trợ `--instance`, `--instance-dir`, log và vẽ hình. |
| `vrpcc/instance.py` | Định nghĩa mô hình dữ liệu `VRPCCInstance`: ma trận khoảng cách, ma trận tương thích, đọc/ghi JSON, tính chi phí tuyến. |
| `vrpcc/approx_algorithm.py` | Hiện thực Algorithm 1 và Algorithm 2 của bài báo. Đây là lõi thuật toán xấp xỉ. |
| `vrpcc/k_tsp_oracle.py` | Hiện thực oracle k-TSP bicriteria dùng trong Algorithm 1. |
| `vrpcc/local_search.py` | Cải thiện nghiệm sau Algorithm 2 bằng 2-opt và relocation. |
| `vrpcc/plotting.py` | Vẽ biểu đồ thời gian/makespan và bản đồ tuyến đường. |
| `scripts/run_comparison.py` | Chạy thuật toán xấp xỉ kèm MIP để so sánh, có thể bỏ MIP bằng `--skip-mip`. |
| `MIP/vrpcc_mip.py` | Mô hình MIP dùng Gurobi làm baseline so sánh nghiệm. |
| `MIP/instancegen_paper.py` | Tạo bộ dữ liệu kiểu bài báo từ Solomon benchmark. |

## 3. Dữ liệu đầu vào

Một instance VRPCC gồm các thành phần chính:

| Thành phần | Ý nghĩa |
|---|---|
| `dist` hoặc `c` | Ma trận khoảng cách giữa các đỉnh. Đỉnh `0` là depot, các đỉnh `1..n-1` là khách hàng. |
| `u` | Ma trận tương thích. `u[k][j] = 1` nghĩa là xe `k` được phép phục vụ khách `j`. |
| `coords` hoặc `coordinates` | Tọa độ 2D, chỉ dùng để vẽ hình tuyến đường. |
| `name` | Tên instance, ví dụ `c-n21-k6`. |

Trong `VRPCCInstance`:

- `n_nodes`: số đỉnh gồm depot.
- `n_customers`: số khách hàng.
- `m`: số xe.
- `tour_length(route, vehicle)`: tính chi phí tuyến của một xe, đồng thời kiểm tra ràng buộc tương thích.
- `makespan(routes)`: lấy giá trị lớn nhất trong các chi phí tuyến xe.

## 4. Luồng chạy trong `run_selected_instances.py`

File `run_selected_instances.py` được tạo để chạy demo/báo cáo dễ hơn. Thay vì gõ nhiều tham số trên terminal, ta sửa trực tiếp danh sách:

```python
INSTANCE_PATHS = [
    "MIP/data_paper_101/tight/c-n21-k6/c-n21-k6.json",
    "MIP/data_paper_101/tight/r-n21-k6/r-n21-k6.json",
    "MIP/data_paper_101/tight/RC-n21-k6/RC-n21-k6.json",
]
```

Lệnh chạy:

```bash
.venv/bin/python run_selected_instances.py
```

Luồng xử lý của file này:

1. Lấy danh sách instance từ `INSTANCE_PATHS` và `INSTANCE_DIRS`.
2. Với mỗi instance:
   - Đọc file JSON bằng `VRPCCInstance.load_json`.
   - Tạo oracle bằng `make_oracle(inst, beta=BETA)`.
   - Chạy `algorithm_2_vrpcc`.
   - Nếu `USE_LOCAL_SEARCH = True`, chạy thêm `local_search`.
   - In kết quả ra terminal.
   - Lưu một dòng kết quả vào `summary_selected_instances.json`.
   - Vẽ hình tuyến đường nếu instance có tọa độ.
3. Sau khi chạy xong, vẽ biểu đồ tổng hợp `approx_bars.png`.

Các biến cấu hình quan trọng:

| Biến | Ý nghĩa |
|---|---|
| `OUT_DIR` | Thư mục lưu kết quả. Mặc định là `output_selected_instances`. |
| `BETA` | Hệ số bicriteria của oracle. Mặc định `5.0`. |
| `EPS` | Sai số dừng của binary search trên `B`. Mặc định `1e-3`. |
| `USE_LOCAL_SEARCH` | Bật/tắt local search sau Algorithm 2. |
| `MAKE_PLOTS` | Bật/tắt vẽ hình. |
| `WRITE_ALGORITHM_LOG` | Bật/tắt ghi log chi tiết thuật toán. |

## 5. Algorithm 1: MCG-VRP Greedy

Algorithm 1 nằm trong `vrpcc/approx_algorithm.py`, hàm:

```python
algorithm_1_mcg_vrp(inst, X, budget, oracle)
```

Ý tưởng:

1. Ban đầu có tập khách chưa phủ `X' = X`.
2. Duyệt lần lượt từng xe `i`.
3. Với xe `i`, chỉ xét các khách còn lại mà xe này tương thích:

```text
Y = X' ∩ V_i
```

4. Gọi oracle:

```text
O(Y, B, i)
```

Oracle trả về một tour cho xe `i` và tập khách được phủ.

5. Xóa các khách đã phủ khỏi `X'`.
6. Sau khi duyệt hết xe, trả về các tuyến tạm thời và tập khách đã phủ.

Vai trò trong báo cáo:

> Algorithm 1 là bước greedy: với một ngân sách `B` cố định, chương trình lần lượt cho từng xe chọn một tuyến khả thi để phủ được nhiều khách nhất có thể, sau đó loại các khách đã được phủ ra khỏi tập còn lại.

## 6. Algorithm 2: Binary Search trên ngân sách `B`

Algorithm 2 nằm trong `vrpcc/approx_algorithm.py`, hàm:

```python
algorithm_2_vrpcc(inst, oracle, eps=1e-3, beta=5.0)
```

Ý tưởng chính:

1. Khởi tạo:

```text
X = toàn bộ khách hàng
lower = 0
upper = 2 * tổng tất cả cạnh c_ij
```

2. Trong khi `upper - lower >= eps`, lấy:

```text
B = (upper + lower) / 2
```

3. Với ngân sách `B`, chạy nhiều lượt greedy:
   - Mỗi lượt gọi Algorithm 1 trên tập khách chưa phủ.
   - Nếu lượt đó phủ được ít nhất một nửa số khách còn lại, coi lượt đó đạt.
   - Nếu phủ được ít hơn một nửa, ngân sách `B` bị xem là chưa đủ.

4. Nếu với `B` hiện tại có thể phủ hết khách:

```text
upper = B
```

5. Nếu không phủ được:

```text
lower = B
```

6. Khi khoảng `[lower, upper]` đủ nhỏ, trả về nghiệm tốt nhất tìm được.

Ý nghĩa của các giá trị in ra:

| Giá trị | Ý nghĩa |
|---|---|
| `B_lower` | Cận dưới cuối cùng của ngân sách `B`. |
| `B_upper` | Cận trên cuối cùng, cũng là `B*` dùng trong nghiệm cuối. |
| `n_binary_steps` | Số bước binary search. |
| `n_waves_last_feasible` | Số lượt greedy cần để phủ hết khách ở nghiệm feasible cuối. |
| `makespan_algo2` | Makespan trước local search. |
| `approx_ratio_bound` | Cận xấp xỉ lý thuyết `(1 + eps) * beta * ceil(log2(n))`. |

Trong báo cáo có thể nói:

> Algorithm 2 không đoán trực tiếp tuyến xe, mà tìm ngân sách `B` đủ nhỏ bằng binary search. Với mỗi `B`, chương trình kiểm tra xem Algorithm 1 có thể liên tục phủ ít nhất một nửa số khách còn lại hay không. Nếu có, `B` được giảm xuống; nếu không, `B` được tăng lên.

## 7. Oracle k-TSP bicriteria

Oracle nằm trong `vrpcc/k_tsp_oracle.py`, hàm chính:

```python
oracle_k_tsp(inst, Y, budget, vehicle, beta=5.0)
```

Input:

| Tham số | Ý nghĩa |
|---|---|
| `Y` | Tập khách đang xét. |
| `budget` | Ngân sách `B` của Algorithm 2. |
| `vehicle` | Xe đang chạy oracle. |
| `beta` | Hệ số bicriteria. Mặc định `5`. |

Oracle tìm một tour khép kín:

```text
0 -> khách ... -> 0
```

sao cho chi phí không vượt quá:

```text
beta * B
```

Cách cài đặt:

- Nếu số khách trong `Y` nhỏ hoặc bằng `8`, chương trình thử exact bằng tổ hợp và hoán vị.
- Nếu số khách lớn hơn `8`, chương trình dùng greedy:
  - Bắt đầu từ depot.
  - Mỗi bước thêm khách làm tăng chi phí tour khép kín ít nhất.
  - Chỉ thêm nếu vẫn không vượt `beta * B`.
  - Sau đó chạy 2-opt để cải thiện thứ tự đi.

Điểm quan trọng:

> Trong mã nguồn, oracle luôn tính chi phí theo tour khép kín, tức có cả cạnh quay về depot. Điều này giúp kết quả thống nhất với hàm `tour_length`.

## 8. Local search sau Algorithm 2

Local search nằm trong `vrpcc/local_search.py`, hàm:

```python
local_search(inst, routes, max_passes=30)
```

Mục tiêu là giảm makespan sau khi đã có nghiệm từ Algorithm 2.

Hai bước chính:

1. **2-opt trên từng đoạn tuyến**
   - Một route có thể có nhiều đoạn qua depot, ví dụ:

```text
[0, 3, 5, 0, 18, 0]
```

   - Code tách route thành các đoạn `[0, ..., 0]`, rồi chạy 2-opt trên từng đoạn.

2. **Relocation giữa các xe**
   - Tìm xe đang có tuyến dài nhất.
   - Thử lấy từng khách trên xe đó chuyển sang xe khác.
   - Chỉ chấp nhận nếu:
     - Xe mới tương thích với khách.
     - Makespan toàn cục giảm.

Trong báo cáo nên phân biệt rõ:

- `makespan_algo2`: nghiệm trực tiếp từ thuật toán xấp xỉ.
- `makespan_final`: nghiệm sau local search.

Local search giúp nghiệm thực nghiệm tốt hơn, nhưng cận xấp xỉ lý thuyết thuộc về Algorithm 2.

## 9. Kết quả chạy mẫu

Lệnh đã chạy:

```bash
.venv/bin/python run_selected_instances.py
```

Các instance:

```text
c-n21-k6
r-n21-k6
RC-n21-k6
```

Bảng tổng hợp từ `output_selected_instances/summary_selected_instances.json`:

| Instance | Số khách | Số xe | Bước nhị phân | B* | Makespan Algo 2 | Makespan sau LS | Thời gian tổng |
|---|---:|---:|---:|---:|---:|---:|---:|
| c-n21-k6 | 20 | 6 | 23 | 16.1245 | 216.9306 | 138.2159 | 0.089s |
| r-n21-k6 | 20 | 6 | 24 | 13.4165 | 223.5229 | 135.9524 | 4.053s |
| RC-n21-k6 | 20 | 6 | 24 | 18.0714 | 233.0794 | 170.0572 | 0.385s |

Nhận xét:

- Cả ba instance đều có 20 khách và 6 xe.
- Sau local search, makespan giảm rõ so với nghiệm Algorithm 2 ban đầu.
- Instance `r-n21-k6` mất thời gian cao hơn hai instance còn lại trong lần chạy mẫu, do quá trình oracle/greedy và cấu trúc tương thích làm số phép thử nhiều hơn.
- Cận xấp xỉ lý thuyết trong ví dụ là:

```text
(1 + eps) * beta * ceil(log2(n_customers))
= (1 + 0.001) * 5 * ceil(log2(20))
= 25.025
```

## 10. File đầu ra dùng cho báo cáo

Sau khi chạy `run_selected_instances.py`, thư mục `output_selected_instances/` có các file:

| File | Dùng để làm gì |
|---|---|
| `summary_selected_instances.json` | Dữ liệu tổng hợp theo từng instance. Dùng để lập bảng báo cáo. |
| `approx_algorithm.log` | Log chi tiết từng bước binary search/greedy. Dùng để kiểm tra hoặc đưa phụ lục. |
| `approx_bars.png` | Biểu đồ tổng hợp thời gian và makespan. |
| `routes_paper_c-n21-k6.png` | Hình tuyến đường của instance `c-n21-k6`. |
| `routes_paper_r-n21-k6.png` | Hình tuyến đường của instance `r-n21-k6`. |
| `routes_paper_RC-n21-k6.png` | Hình tuyến đường của instance `RC-n21-k6`. |

Khi viết báo cáo, không nên đưa toàn bộ log terminal vào phần chính. Nên dùng:

1. Bảng tổng hợp.
2. Hình tuyến đường.
3. Một đoạn giải thích ngắn về `B*`, makespan và local search.
4. Log chi tiết để ở phụ lục nếu cần.

## 11. Gợi ý cách trình bày khi thuyết trình

Có thể trình bày theo thứ tự sau:

1. **Giới thiệu bài toán**

   > Bài toán VRPCC yêu cầu lập tuyến cho nhiều xe sao cho mỗi khách được phục vụ đúng một lần, mỗi xe chỉ được phục vụ những khách tương thích, và mục tiêu là giảm chi phí tuyến lớn nhất trong đội xe.

2. **Mô hình dữ liệu**

   > Trong mã nguồn, mỗi instance gồm ma trận khoảng cách `c_ij` và ma trận tương thích `u[k][j]`. Đỉnh `0` là depot, các đỉnh còn lại là khách hàng.

3. **Thuật toán xấp xỉ**

   > Thuật toán chính là Algorithm 2. Nó binary search trên ngân sách `B`. Với mỗi `B`, chương trình gọi Algorithm 1 để kiểm tra có thể phủ dần ít nhất một nửa số khách còn lại hay không.

4. **Oracle**

   > Algorithm 1 cần một oracle k-TSP. Trong chương trình, nếu tập khách nhỏ thì oracle giải exact bằng thử hoán vị; nếu lớn thì dùng greedy thêm khách có chi phí tăng nhỏ nhất, sau đó cải thiện bằng 2-opt.

5. **Cải thiện nghiệm**

   > Sau khi có nghiệm từ Algorithm 2, chương trình chạy local search gồm 2-opt và relocation. Vì vậy kết quả cuối thường tốt hơn makespan ban đầu.

6. **Kết quả thực nghiệm**

   > Với 3 instance n21-k6, local search giảm makespan đáng kể. Ví dụ instance `c-n21-k6` giảm từ `216.9306` xuống `138.2159`.

## 12. Điểm cần lưu ý khi bị hỏi

**B* có phải là makespan không?**

Không. `B*` là ngân sách dùng cho mỗi lần gọi oracle trong một lượt greedy. Tuyến cuối có thể là kết quả nối nhiều lượt, nên makespan cuối có thể lớn hơn `beta * B*`.

**Vì sao có local search?**

Algorithm 2 cho nghiệm có bảo đảm lý thuyết. Local search là bước hậu xử lý thực nghiệm để cải thiện nghiệm, đặc biệt giảm tuyến dài nhất.

**Tại sao dùng beta = 5?**

Theo phần thực nghiệm/bicriteria oracle trong bài báo, oracle k-TSP dùng hệ số xấp xỉ `5`. Code đặt mặc định `BETA = 5.0`.

**MIP dùng để làm gì?**

MIP trong thư mục `MIP/` là baseline giải chính xác/tối ưu bằng Gurobi để so sánh trên instance nhỏ hoặc khi license cho phép. Khi chỉ trình bày thuật toán xấp xỉ thì không cần chạy MIP.

**Vì sao route có nhiều số 0 ở giữa?**

Số `0` là depot. Algorithm 2 có thể nối nhiều lượt greedy lại với nhau, nên một xe có thể có dạng:

```text
[0, 3, 5, 0, 18, 0]
```

Nghĩa là xe đi một chuyến `0 -> 3 -> 5 -> 0`, rồi một chuyến khác `0 -> 18 -> 0`.

## 13. Kết luận ngắn

Mã nguồn đã hiện thực đầy đủ pipeline thực nghiệm cho VRPCC:

- Đọc instance có ràng buộc tương thích.
- Chạy Algorithm 1 và Algorithm 2 theo bài báo.
- Dùng oracle k-TSP bicriteria.
- Cải thiện nghiệm bằng local search.
- Xuất bảng, log và hình vẽ phục vụ báo cáo.

Phần nên đưa vào báo cáo chính là bảng kết quả và hình tuyến đường; phần log chi tiết nên dùng để giải thích hoặc đưa vào phụ lục.
