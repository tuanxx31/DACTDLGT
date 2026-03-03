# VRPCC Theo Paper: Kiểm Tra Thuật Toán + Hướng Dẫn Chạy Dễ Hiểu

## 1) Mục tiêu của repo này

Repo hiện tại là bản **demo dễ hiểu** cho bài báo:

**“An Approximation Algorithm for Vehicle Routing with Compatibility Constraints”**

Mục tiêu:
- Giữ đúng khung thuật toán chính trong paper (Algorithm 1 + Algorithm 2).
- Có giao diện web để người không chuyên vẫn chạy được.
- Có chế độ CLI để chạy trực tiếp thuật toán.
- Có hậu xử lý thực nghiệm theo paper: `2-opt + relocation`.

---

## 2) Kết luận kiểm tra: Code đã bám paper đến đâu?

### 2.1 Các phần bám đúng paper

Trong `vrpcc_core.py`:
- `algorithm1_mcg_vrp(...)` triển khai đúng **Algorithm 1**:
  - Khởi tạo tập chưa phủ `X'`.
  - Duyệt từng xe.
  - Gọi oracle trên `X' ∩ V_i`.
  - Loại bỏ node đã phủ khỏi `X'`.
- `solve_vrpcc_approx(...)` triển khai đúng khung **Algorithm 2**:
  - Binary-search trên ngân sách `B`.
  - Với mỗi `B`, lặp gọi Algorithm 1 cho đến khi phủ hết hoặc thất bại.
  - Điều kiện thất bại đúng paper: nếu mỗi vòng không phủ được ít nhất một nửa tập hiện tại (`|covered| < |X|/2`), thì `Solve = false`.
  - Nếu solve được thì cập nhật cận trên `u = B`, ngược lại cập nhật cận dưới `l = B`.
- Sau khi có nghiệm từ Algorithm 1 + 2, code áp dụng local search như paper mô tả ở phần thực nghiệm:
  - `2-opt` cho từng tuyến.
  - `Relocation` nhắm vào makespan:
    - luôn chọn xe có tuyến dài nhất hiện tại,
    - thử chuyển từng khách từ xe này sang xe tương thích khác,
    - chèn vào vị trí tốt nhất,
    - lặp cho tới khi makespan không giảm thêm.

### 2.2 Các điểm khác paper (có chủ đích)

1. **Oracle**
- Paper dùng orienteering/k-TSP approximation (đa thức, có hệ số xấp xỉ).
- Code hiện tại dùng `oracle_orienteering_exact(...)` (exact, hàm mũ) để demo dễ kiểm chứng trên instance nhỏ.
- Tác động:
  - Bám đúng logic thuật toán.
  - Không bám độ phức tạp đa thức như bản lý thuyết trong paper.

2. **Bảo đảm xấp xỉ lý thuyết**
- Paper nêu bảo đảm dạng `(1+eps) * beta * ceil(log2 n)` trong bối cảnh oracle bicriteria phù hợp.
- Code demo có thể cho kết quả tốt hơn/thực nghiệm hơn vì oracle exact nhỏ, nhưng **không nhằm chứng minh lại bound đa thức** của paper.

3. **Giả định metric của paper**
- Paper giả định khoảng cách metric/symmetric.
- Demo mặc định dùng Euclidean (đáp ứng tốt), nhưng nếu bạn tự nhập `dist` thì cần tự đảm bảo dữ liệu hợp lý.

---

## 3) Cấu trúc file

| File | Vai trò |
|---|---|
| `vrpcc_core.py` | Cốt lõi thuật toán (Algorithm 1, Algorithm 2, oracle exact, hậu xử lý 2-opt + relocation, formatter log) |
| `vrpcc_paper_ui_web.py` | Giao diện web tiếng Việt (JSON dễ hiểu + kỹ thuật) |
| `vrpcc_run_core.py` | Chạy thuật toán từ CLI (không cần web) |

---

## 4) Luồng hoạt động thuật toán (dễ hiểu)

## Bước A: Chuẩn bị dữ liệu
- Node `0` là kho/depot.
- Các node `1..n` là khách hàng.
- Mỗi xe có tập khách hàng tương thích (`compatible[k]`).

## Bước B: Algorithm 1 (MCG-VRP Greedy)
- Input: tập khách chưa phủ `X`, ngân sách `B`.
- Với từng xe:
  - Chọn route phủ được nhiều khách nhất trong `X` (có xét tương thích).
  - Loại các khách vừa phủ khỏi `X`.
- Output: 1 route/xe cho vòng hiện tại.

## Bước C: Algorithm 2 (Binary-search + lặp phủ)
- Đoán ngân sách `B` bằng binary-search.
- Với ngân sách `B`, lặp gọi Algorithm 1:
  - Nếu một vòng không phủ được ít nhất 1/2 tập còn lại -> `B` quá nhỏ (fail).
  - Nếu phủ hết khách -> `B` khả thi (success).
- Cập nhật cận `l/u` và tiếp tục cho đến khi `u - l < eps`.

## Bước D: Xuất kết quả
- In makespan (độ dài lớn nhất trong các xe).
- In route theo từng xe, từng vòng.
- In log binary-search và log mức phủ theo vòng.

## Bước E: Hậu xử lý theo paper (thực nghiệm)
- 2-opt trên từng tuyến xe.
- Relocation theo mục tiêu makespan:
  - chọn tuyến dài nhất,
  - chuyển khách sang xe tương thích có vị trí chèn tốt nhất,
  - chấp nhận nếu makespan giảm,
  - lặp tới khi không giảm được nữa.

---

## 5) Cách chạy

## 5.1 Cách dễ nhất: UI web

```bash
cd /Users/tuna/Code/DACTDLGT
/usr/bin/python3 vrpcc_paper_ui_web.py --port 8777
```

Mở trình duyệt:
- `http://127.0.0.1:8777`

Trong UI:
1. Bấm **Nạp mẫu dễ hiểu**.
2. Chọn bật/tắt **Hậu xử lý (2-opt + relocation)**.
3. Bấm **Giải bài toán**.
4. Xem tuyến đường + nhật ký kết quả.

## 5.2 Chạy trực tiếp thuật toán (CLI)

```bash
cd /Users/tuna/Code/DACTDLGT
python3 vrpcc_run_core.py
```

Chạy với file JSON kỹ thuật:

```bash
python3 vrpcc_run_core.py --input /đường/dẫn/instance.json --eps 0.01 --beta 1.0
```

Tắt hậu xử lý local search để so sánh:

```bash
python3 vrpcc_run_core.py --input /đường/dẫn/instance.json --no-local-search
```

---

## 6) Định dạng JSON đầu vào

UI web hỗ trợ 2 kiểu:

1. **Dạng dễ hiểu (tiếng Việt)**: `điểm_xuất_phát`, `xe`, `khách_hàng`, `xe_phù_hợp`, `tay_nghề_cần`.
2. **Dạng kỹ thuật**: `points + compatible` hoặc `dist + compatible`.

Ví dụ dạng kỹ thuật:

```json
{
  "points": [[0, 0], [1, 2], [2, 1], [3, 2]],
  "compatible": [
    [1, 2],
    [2, 3]
  ]
}
```

---

## 7) Ý nghĩa tham số

- `eps`: độ chính xác của binary-search.
  - Nhỏ hơn -> sát hơn, chạy lâu hơn.
- `beta`: hệ số nới ngân sách của oracle.
  - `beta = 1.0` là chặt nhất.
  - Lớn hơn có thể dễ tìm nghiệm hơn (nhưng nới lỏng ngân sách mỗi vòng).
- `--no-local-search` (CLI): tắt bước 2-opt + relocation.

---

## 8) Lưu ý hiệu năng

- Oracle hiện tại là exact (hàm mũ), nên phù hợp demo nhỏ.
- Nếu cần chạy lớn như benchmark paper, nên thay oracle bằng k-TSP/orienteering approximation đa thức.
- Local search 2-opt + relocation giúp nghiệm thực nghiệm tốt hơn, nhưng không thay đổi bản chất bảo đảm xấp xỉ của phần lõi.

---

## 9) Kiểm tra nhanh sau khi sửa

```bash
python3 -m py_compile vrpcc_core.py vrpcc_paper_ui_web.py vrpcc_run_core.py
python3 vrpcc_run_core.py
```

Nếu 2 lệnh trên chạy được là luồng core đang ổn.
