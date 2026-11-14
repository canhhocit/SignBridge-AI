# Bảng Mẫu Quy Chuẩn Kiểm Thử Ngôn Ngữ Ký Hiệu (VSL Test Benchmark)

> **Tài liệu tham chiếu:** [luong-xu-ly-chinh.md §6.1, §6.2, §7](file:///C:/personal/SignBridge-AI/docs/luong-xu-ly-chinh.md)  
> **Phiên bản:** 1.0 (Áp dụng cho bộ 20 ký hiệu chuẩn đóng & Mô hình Hybrid TFLite 2.764 nhãn QIPEDC)

---

## 1. Điều Kiện Môi Trường Kiểm Thử Chuẩn

Để kết quả nhận diện thị giác máy tính đạt độ chính xác cao nhất (≥ 80%), người thử nghiệm cần tuân thủ các điều kiện sau:

* **Khoảng cách Camera:** Đứng hoặc ngồi cách camera từ **0.8m đến 1.2m**.
* **Khung hình hiển thị:** Đảm bảo toàn bộ **thân trên (từ ngực lên đỉnh đầu) và hai bàn tay** luôn nằm trọn trong khung viền xanh trên màn hình.
* **Ánh sáng:** Đủ sáng trong phòng, tránh ngồi ngược sáng (không ngồi quay lưng vào cửa sổ hoặc bóng đèn chói).
* **Nhịp điệu động tác:**
  * Chọn chế độ **`4 frames (1.5s)`** khi test **1 cử chỉ đơn**.
  * Chọn chế độ **`8 frames (3.0s)`** khi test **chuỗi 2 cử chỉ liên tiếp**.
  * Khi màn hình đếm ngược `3 - 2 - 1` kết thúc và hiện chấm đỏ 🔴, bắt đầu thực hiện động tác dứt khoát.

---

## 2. Bảng Ma Trận Kiểm Thử Ký Hiệu (VSL Test Matrix)

### Nhóm A: Bối Cảnh Hiệu Thuốc & Y Tế (`context = PHARMACY`)

| Mã TC | Cử chỉ ký hiệu | Hướng dẫn động tác tay | Chế độ | Đầu ra AI kỳ vọng | Kết quả thực tế | Đánh giá |
|:---|:---|:---|:---:|:---|:---:|:---:|
| **TC-PHA-01** | `ĐAU` + `ĐẦU` | Day xoay ngón tay trước thái dương, nhăn mặt ➔ chỉ ngón trỏ vào đầu | 8 frames (3.0s) | **Glosses:** `["ĐAU", "ĐẦU"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ em bị đau đầu ạ, xin tư vấn giúp em với ạ."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-PHA-02** | `ĐAU` + `BỤNG` | Day xoay bàn tay trước ngực ➔ xoa nhẹ lòng bàn tay lên bụng | 8 frames (3.0s) | **Glosses:** `["ĐAU", "BỤNG"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ em bị đau bụng ạ, nhờ anh/chị xem giúp."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-PHA-03** | `SỐT` | Mu bàn tay đặt lên trán (động tác đo nhiệt độ) giữ 1.5s | 4 frames (1.5s) | **Glosses:** `["SỐT"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ em cảm thấy bị sốt ạ, nhờ tư vấn giúp em."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-PHA-04** | `THUỐC` + `MUA` | Chụm ngón tay đưa vào miệng ➔ ngửa bàn tay đưa ra trước | 8 frames (3.0s) | **Glosses:** `["THUỐC", "MUA"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ cho em hỏi mua thuốc này với ạ."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-PHA-05** | `HAI` + `NGÀY` | Giơ 2 ngón tay (chữ V) ➔ ngón trỏ vẽ vòng cung mặt trời lặn | 8 frames (3.0s) | **Glosses:** `["HAI", "NGÀY"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ khoảng hai ngày rồi ạ."* | [ ] Pass<br>[ ] Fail | `__%` |

---

### Nhóm B: Bối Cảnh Quán Cà Phê & Đồ Uống (`context = CAFE`)

| Mã TC | Cử chỉ ký hiệu | Hướng dẫn động tác tay | Chế độ | Đầu ra AI kỳ vọng | Kết quả thực tế | Đánh giá |
|:---|:---|:---|:---:|:---|:---:|:---:|
| **TC-CAF-01** | `CÀ PHÊ` + `ĐÁ` | Hai tay nắm, tay trên xoay tròn khuấy ➔ hai nắm tay gõ nhẹ vào nhau | 8 frames (3.0s) | **Glosses:** `["CÀ PHÊ", "ĐÁ"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Cho mình một cà phê đá nhé ạ, cảm ơn bạn."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-CAF-02** | `CÀ PHÊ` + `MANG ĐI` | Động tác khuấy ly ➔ hai tay nắm hướng lên xách quai túi đưa ra xa | 8 frames (3.0s) | **Glosses:** `["CÀ PHÊ", "MANG ĐI"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Cho mình một cà phê mang đi nhé ạ."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-CAF-03** | `CÀ PHÊ` (Đơn) | Hai tay nắm, tay trên xoay tròn khuấy ly trong 1.5s | 4 frames (1.5s) | **Glosses:** `["CÀ PHÊ"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ cho em xin một ly cà phê nhé ạ."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-CAF-04** | `MỘT` + `CÀ PHÊ` | Giơ 1 ngón trỏ thẳng lên ➔ làm động tác khuấy cà phê | 8 frames (3.0s) | **Glosses:** `["MỘT", "CÀ PHÊ"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Cho mình một ly cà phê nhé bạn."* | [ ] Pass<br>[ ] Fail | `__%` |

---

### Nhóm C: Bối Cảnh Hành Chính Công (`context = PUBLIC`)

| Mã TC | Cử chỉ ký hiệu | Hướng dẫn động tác tay | Chế độ | Đầu ra AI kỳ vọng | Kết quả thực tế | Đánh giá |
|:---|:---|:---|:---:|:---|:---:|:---:|
| **TC-PUB-01** | `GIẤY TỜ` + `Ở ĐÂU` | Hai bàn tay phẳng mở úp vào nhau rồi lật mở ➔ ngửa 2 tay ngang ngực lắc nhẹ | 8 frames (3.0s) | **Glosses:** `["GIẤY TỜ", "Ở ĐÂU"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Chào anh/chị, cho em hỏi nộp giấy tờ ở đâu ạ?"* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-PUB-02** | `GIẤY TỜ` (Đơn) | Hai bàn tay phẳng úp vào nhau rồi lật mở như trang sách | 4 frames (1.5s) | **Glosses:** `["GIẤY TỜ"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ em muốn hỏi về phần giấy tờ này ạ."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-PUB-03** | `Ở ĐÂU` (Đơn) | Hai bàn tay ngửa ngang ngực hơi lắc sang 2 bên, mặt dò hỏi | 4 frames (1.5s) | **Glosses:** `["Ở ĐÂU"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ cho em hỏi quầy ở đâu vậy ạ?"* | [ ] Pass<br>[ ] Fail | `__%` |

---

### Nhóm D: Giao Tiếp Chung & Thanh Toán (`context = CUSTOM`)

| Mã TC | Cử chỉ ký hiệu | Hướng dẫn động tác tay | Chế độ | Đầu ra AI kỳ vọng | Kết quả thực tế | Đánh giá |
|:---|:---|:---|:---:|:---|:---:|:---:|
| **TC-COM-01** | `XIN CHÀO` | Bàn tay mở phẳng ngang thái dương, vẫy nhẹ sang phải | 4 frames (1.5s) | **Glosses:** `["XIN CHÀO"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ em chào anh/chị ạ."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-COM-02** | `CẢM ƠN` | Đầu ngón tay chạm cằm/môi dưới rồi đưa thẳng ra trước | 4 frames (1.5s) | **Glosses:** `["CẢM ƠN"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ em cảm ơn anh/chị nhiều ạ."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-COM-03** | `THANH TOÁN` | Ngón cái và ngón trỏ cọ xát vào nhau (đếm tiền) trước ngực | 4 frames (1.5s) | **Glosses:** `["THANH TOÁN"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ cho em thanh toán với ạ."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-COM-04** | `BAO NHIÊU` | Hai bàn tay ngửa ngang bụng, các ngón tay rung rung hướng lên | 4 frames (1.5s) | **Glosses:** `["BAO NHIÊU"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ món này hết bao nhiêu tiền vậy ạ?"* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-COM-05** | `CÓ` (Đồng ý) | Bàn tay nắm lại, ngón cái giơ lên 👍 gật nhẹ 1–2 lần | 4 frames (1.5s) | **Glosses:** `["CÓ"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ vâng, đúng rồi ạ."* | [ ] Pass<br>[ ] Fail | `__%` |
| **TC-COM-06** | `KHÔNG` (Từ chối) | Bàn tay xoè ngang ngực lắc qua lại sang 2 bên 👎 | 4 frames (1.5s) | **Glosses:** `["KHÔNG"]`<br>**Confidence:** ≥ 70%<br>**Câu nói:** *"Dạ không, em không cần đâu ạ."* | [ ] Pass<br>[ ] Fail | `__%` |

---

### Nhóm E: Kịch Bản Biên & Cơ Chế Dự Phòng (Edge Cases & Fallback)

| Mã TC | Kịch bản kiểm thử | Hành động thực hiện | Kỳ vọng hệ thống xử lý | Mục đích kiểm tra |
|:---|:---|:---|:---|:---|
| **TC-EDG-01** | Ký quá nhanh / Mờ tay | Vung tay qua lại lung tung trước camera, không rõ hình dáng | • `confidence` < 0.70 hoặc có `UNKNOWN`<br>• `spoken_sentence` = `""` (Rỗng)<br>• **Bắt buộc hiện thẻ gợi ý** để người dùng chạm xác nhận | Chống nhận diện sai, không phát loa bậy |
| **TC-EDG-02** | Cử chỉ ngoài ngữ cảnh | Đang chọn `PHARMACY` nhưng lại làm cử chỉ `CÀ PHÊ` | • Ký hiệu `CÀ PHÊ` bị lọc thành `UNKNOWN`<br>• Câu phát loa rỗng, đẩy ra thẻ nhà thuốc | Bảo vệ phạm vi ngữ nghĩa của bối cảnh |
| **TC-EDG-03** | Không cử động (Đứng yên) | Đứng yên nhìn vào camera, không giơ tay | • Trả mã lỗi `422 NO_SIGN_DETECTED`<br>• Báo nhắc nhở người dùng thực hiện cử chỉ | Tránh xử lý khung hình rác |

---

## 3. Biểu Mẫu Tổng Kết Nghiệm Thu (Acceptance Summary)

* **Tổng số kịch bản:** 20 Test Cases
* **Số ca Đạt (Pass):** `___ / 20` (Đạt tỷ lệ: `___ %`)
* **Tiêu chuẩn Nghiệm thu Đạt:** Tỷ lệ chính xác **≥ 80%**, Không tự ý bịa triệu chứng hoặc giá tiền ngoài cử chỉ.
* **Người thực hiện kiểm thử:** `____________________`
* **Ngày kiểm thử:** `____ / ____ / 2026`
