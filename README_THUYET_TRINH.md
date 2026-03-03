# README Thuyết Trình VRPCC (Dựa Trên Kết Quả Bạn Đang Có)

## 1) Bài toán đang giải là gì?

Ta đang giải **VRPCC**:
- Nhiều xe xuất phát từ 1 kho (node 0).
- Mỗi khách hàng chỉ được phục vụ bởi một số xe tương thích (`xe_phù_hợp`).
- Mục tiêu không phải tổng quãng đường nhỏ nhất, mà là:
  - **Makespan** = quãng đường lớn nhất trong các xe.
  - Tối ưu để xe “nặng nhất” cũng nhẹ nhất có thể.

---

## 2) Giải thích output bạn vừa nhận

Bạn có output:

- `Số khách hàng: 8, Số xe: 3`
- `Độ dài lớn nhất (makespan): 11.2558`
- `Hậu xử lý (2-opt + relocation): 17.6364 -> 11.2558`
- `Ngân sách B được chọn: 10.0031`
- `Số vòng binary-search: 15`

Ý nghĩa:

1. `B` là “ngân sách thử” cho **mỗi vòng** của thuật toán.
2. Thuật toán dùng binary-search để tìm `B` nhỏ nhất mà vẫn “phủ đủ nhanh” theo điều kiện paper.
3. Với `B = 10.0031`, thuật toán thành công.
4. Dù `B` khoảng 10, mỗi xe có thể chạy nhiều vòng, nên tổng của 1 xe có thể > 10.
5. Sau đó chạy hậu xử lý theo paper (2-opt + relocation) để giảm makespan thêm.

---

## 3) Vì sao makespan còn giảm được sau bước hậu xử lý?

Trong output:

- Trước local search:
  - Xe 1 nặng nhất, makespan = `17.6364`.
- Sau local search:
  - Relocation chuyển bớt khách khỏi xe dài nhất sang xe tương thích.
  - Makespan giảm còn `11.2558`.

Nói ngắn gọn khi thuyết trình:
- “Em bám paper: sau khi có nghiệm xấp xỉ, em chạy 2-opt và relocation nhắm thẳng makespan; kết quả giảm từ 17.6364 xuống 11.2558.”

---

## 4) Cách đọc bảng `Nhật ký binary-search`

Ví dụ 1 dòng:

`iter=10 ... B=9.9632 -> KHÔNG ĐẠT, số_vòng=3`

Diễn giải:
- Ở lần thử thứ 10, ngân sách `B=9.9632` quá thấp.
- Trong quá trình lặp, có vòng không phủ được ít nhất 1/2 tập khách còn lại.
- Nên thuật toán đánh dấu `KHÔNG ĐẠT` và tăng cận dưới.

Ví dụ dòng đạt:

`iter=15 ... B=10.0031 -> ĐẠT, số_vòng=2`

Diễn giải:
- `B=10.0031` vừa đủ để toàn bộ tiến trình thành công.
- Nên đây là ngân sách khả thi cuối cùng (ở mức chính xác theo `eps`).

---

## 5) Cách đọc phần “Mức độ bao phủ từng vòng”

Bạn có:
- `vòng=1 ... đã_phủ=[1,2,3,5,6,7] còn_lại=[4,8]`
- `vòng=2 ... đã_phủ=[4,8] còn_lại=[]`

Ý nghĩa:
- Vòng 1 phủ 6/8 khách (đạt điều kiện phủ ít nhất một nửa).
- Vòng 2 phủ nốt 2 khách còn lại.
- Kết thúc bài toán.

---

## 6) Tóm tắt thuật toán để nói trong 45 giây

“Mỗi lần tôi đoán một ngân sách `B`. Với `B` đó, mỗi xe chọn tour phủ được nhiều khách mới nhất có thể (có xét tương thích). Nếu một vòng phủ dưới một nửa số khách còn lại thì `B` bị coi là quá nhỏ. Tôi dùng binary-search để tìm `B` nhỏ nhất còn khả thi. Sau đó chạy hậu xử lý 2-opt và relocation: luôn chọn xe dài nhất, chuyển khách sang xe tương thích nếu makespan giảm, lặp tới khi không giảm nữa.”

---

## 7) Khớp với paper ở đâu?

- Đúng khung **Algorithm 1 + Algorithm 2**.
- Điều kiện `ĐẠT/KHÔNG ĐẠT` bám đúng điều kiện “phủ ít nhất 1/2”.
- Khác biệt có chủ đích:
  - Oracle hiện tại dùng bản exact (hàm mũ) để demo dễ kiểm chứng trên instance nhỏ.
  - Paper gốc nhấn mạnh oracle xấp xỉ đa thức (k-TSP/orienteering) cho bài toán lớn.
  - Có local search 2-opt + relocation đúng hướng mô tả ở phần thực nghiệm của paper.

---

## 8) Gợi ý bố cục slide thuyết trình (5–7 phút)

1. Slide 1: Bài toán VRPCC và mục tiêu makespan.
2. Slide 2: Dữ liệu đầu vào (kho, 8 khách, 3 xe, tương thích tay nghề).
3. Slide 3: Ý tưởng Algorithm 1 + 2 (hình flow đơn giản).
4. Slide 4: Kết quả chính:
   - `B ~ 10.0031`
   - Makespan trước/sau local search: `17.6364 -> 11.2558`
   - Nhấn mạnh relocation giúp san tải xe nặng nhất.
5. Slide 5: Nhật ký binary-search (2 dòng đạt/không đạt minh họa).
6. Slide 6: Kết luận + giới hạn (oracle exact cho demo nhỏ).

---

## 9) Chạy lại đúng demo hiện tại

```bash
cd /Users/tuna/Code/DACTDLGT
/usr/bin/python3 vrpcc_paper_ui_web.py --port 8777
```

Mở:
- http://127.0.0.1:8777

Trong UI:
1. `Nạp mẫu dễ hiểu`
2. `Giải bài toán`
3. Đọc `Kết quả / Nhật ký` theo phần giải thích ở trên.
