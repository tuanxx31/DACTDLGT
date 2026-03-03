# Cheat Sheet 1 Trang – Thuyết Trình VRPCC

## 1) Mở bài (20–30 giây)

“Bài toán em giải là VRPCC: nhiều xe xuất phát từ kho, mỗi khách hàng chỉ tương thích với một số xe theo tay nghề.  
Mục tiêu là giảm **makespan**: tức quãng đường lớn nhất trong các xe, để workload cân bằng hơn.”

---

## 2) Input demo đang dùng

- 1 kho (node 0)
- 8 khách hàng
- 3 xe, mỗi xe có tay nghề khác nhau
- Mỗi khách có `xe_phù_hợp` (ràng buộc tương thích)

---

## 3) Thuật toán nói ngắn gọn (40–60 giây)

“Em dùng khung Algorithm 1 + Algorithm 2 trong paper:

1. Đoán ngân sách `B` bằng binary-search.  
2. Với mỗi `B`, chạy nhiều vòng:
   - Mỗi xe chọn route phủ được nhiều khách mới nhất trong giới hạn ngân sách.
   - Nếu một vòng phủ < 1/2 số khách còn lại thì `B` bị coi là quá nhỏ.
3. Tìm `B` nhỏ nhất còn khả thi, ghép các vòng lại thành route cuối cho từng xe.
4. Hậu xử lý theo paper: 2-opt + relocation từ xe dài nhất sang xe tương thích, lặp đến khi makespan không giảm thêm.”

---

## 4) Đọc kết quả hiện tại (đúng số của bạn)

- Makespan sau hậu xử lý: **11.2558**
- Makespan trước hậu xử lý: **17.6364**
- Ngân sách tìm được: **B = 10.0031**
- Binary-search: **15 vòng**

Giải thích:
- Trước local search, xe 1 là nút cổ chai.
- Sau 2-opt + relocation, hệ thống dồn lại tải nên makespan giảm còn 11.2558.

---

## 5) Câu chốt kỹ thuật (20 giây)

- “Code bám đúng khung thuật toán của paper ở mức luồng giải.”
- “Điểm khác là oracle hiện tại dùng bản exact để demo nhỏ, còn paper gốc hướng tới oracle xấp xỉ đa thức cho quy mô lớn.”

---

## 6) Nếu bị hỏi “ĐẠT/KHÔNG ĐẠT là gì?”

Trả lời nhanh:
- `ĐẠT`: với `B` đó, mỗi vòng phủ đủ nhanh (ít nhất 1/2 tập còn lại) và cuối cùng phủ hết.
- `KHÔNG ĐẠT`: có vòng phủ quá ít, nên `B` còn thấp.

---

## 7) Nếu bị hỏi “Tại sao B ~ 10 mà makespan > 10?”

“Vì `B` là ngân sách cho **mỗi vòng**, không phải tổng cả bài toán.  
Một xe có thể chạy nhiều vòng, nên tổng quãng đường của xe đó có thể lớn hơn `B`.”

---

## 8) Kết luận 1 câu

“Mô hình này bám đúng hướng paper: Algorithm 1+2 để có nghiệm xấp xỉ, rồi 2-opt + relocation để giảm thêm makespan trong thực nghiệm.”
