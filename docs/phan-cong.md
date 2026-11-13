# Phân công & kế hoạch — SignBridge

> **Nguồn:**
> - Từ docx: 4 vai trò (`Mo_ta_y_tuong.docx` §12), tổng thời gian 5 tiếng (§8, §12), tiêu chí hoàn thành (§8, §15), data model (§11).
> - **Không có trong docx — agent đề xuất:** mọi mốc giờ, thư viện, tên hàm, số frame, ngưỡng `confidence`. Team tự điều chỉnh.
> - Luồng và đặc tả API: `docs/luong-xu-ly-chinh.md`.

## 1. Tổng quan

| Người | Vai trò | Repo | Trọng tâm |
|---|---|---|---|
| **TV1** | Mobile UI/UX Accessibility | mobile | Màn hình chia đôi 180°, thẻ từ khóa, hiển thị chữ lớn, rung |
| **TV2** | Mobile thiết bị & Local Storage | mobile | Camera ký hiệu, ghi âm, loa TTS, SQLite, offline, gọi API |
| **TV3** | AI Prompt & Speech Pipeline | backend | Chọn LLM/STT, 3 prompt, thử nhận diện ký hiệu |
| **TV4** | Backend | backend | Spring Boot 4 endpoint, ghép AI, chạy backend, test end-to-end |

## 2. Mốc chung (đề xuất)

| Giờ | Mốc | Ai |
|---|---|---|
| 0:00–0:30 | Chốt hợp đồng API, nhà cung cấp AI, nơi chạy backend | Cả team |
| 0:30 | Endpoint **giả** trả JSON mẫu chạy được | TV4 |
| 1:30 | Quyết định đi tiếp/đổi hướng nhận diện ký hiệu | TV3 báo, cả team chốt |
| 3:00 | Backend gọi AI thật; mobile chạy đủ 2 chiều với endpoint giả | TV2, TV3, TV4 |
| 4:00 | Mobile gọi backend thật trên điện thoại thật | TV2, TV4 |
| 5:00 | Đạt 3 tiêu chí docx §15 | Cả team |

---

## 3. TV1 — Mobile UI/UX Accessibility

- [ ] Màn chọn ngữ cảnh: Quán ăn, Hiệu thuốc, Hành chính, Tự do.
- [ ] Màn Split-Screen: nửa trên xoay 180° cho nhân viên, nửa dưới cho người khiếm thính.
- [ ] Nửa dưới — nút nhấn giữ **Ký hiệu**.
- [ ] Nửa dưới — bảng thẻ từ khóa, chọn 1–3 thẻ.
- [ ] Nửa dưới — vùng hiện `glosses` + `suggestedChips` khi `confidence` thấp.
- [ ] Nửa dưới — vùng tóm tắt: `summary` chữ lớn, tô đậm `highlights`, icon theo `iconCode`, 3 nút `quickReplies`.
- [ ] Nửa trên — `spoken_sentence` cỡ lớn + nút nhấn giữ **Mic**.
- [ ] Màn thêm/xoá thẻ cá nhân.
- [ ] Rung khi phát loa xong và khi nhân viên bắt đầu nói.
- [ ] Chữ lớn, tương phản cao; hai người đối diện đọc rõ mà không xoay máy.

---

## 4. TV2 — Mobile thiết bị & Local Storage

- [ ] SQLite 4 bảng: `ContextPreset`, `QuickChip`, `ConversationSession`, `MessageTurn` + thẻ mẫu cho 4 ngữ cảnh.
- [ ] Thêm/xoá thẻ cá nhân, tăng `usageCount`, lưu và đọc lịch sử hội thoại.
- [ ] Camera ký hiệu: lấy 4 frame mỗi 1,5 giây, clip 1,5–6 giây (4–16 frame), ≤ 640px, JPEG ≤ 250KB.
- [ ] Ghi âm m4a nhấn giữ.
- [ ] TTS đọc tiếng Việt, báo khi đọc xong.
- [ ] Gọi 4 API (`/health`, `/sign`, `/expand`, `/summarize`), timeout 10 giây, xử lý theo `error.code`.
- [ ] Offline: mất mạng → ghép thẻ thành câu mẫu.
- [ ] Force Close → mở lại vẫn còn thẻ cá nhân và lịch sử.
- [ ] Các hàm giao cho TV1 (tên đề xuất):

```ts
recordSign(context, previousIncoming?): Promise<SignResult>
expandChips(context, chips, previousIncoming?): Promise<string>
startRecording(): void
stopAndSummarize(context, previousOutgoing?): Promise<SummaryResult>
speak(sentence, onDone): void
getChips(context) · addChip(...) · deleteChip(id)
saveTurn(...) · getHistory()
checkHealth(): Promise<boolean>
```

---

## 5. TV3 — AI Prompt & Speech Pipeline

- [ ] Chốt nhà cung cấp LLM vision, LLM text, STT + tên biến môi trường cho API key.
- [ ] Chốt bộ ký hiệu (bản đề xuất ở mục 7 `luong-xu-ly-chinh.md`), quay mẫu từng ký hiệu.
- [ ] Kết quả thử nhận diện ký hiệu (tỉ lệ đúng, độ trễ) — **báo trước mốc 1:30**.
- [ ] Prompt `/sign`: frames + `previousIncoming` → `glosses`, `confidence`, `spoken_sentence`, `suggestedChips`.
- [ ] Prompt `/summarize`: tóm tắt ≤ 15 từ, giữ nguyên mọi con số, `highlights`, `iconCode`, 3 `quickReplies`.
- [ ] Prompt `/expand`: thẻ + `previousIncoming` → câu lịch sự theo ngữ cảnh.
- [ ] JSON schema output cho cả 3 prompt; parse được trong mọi lần thử.
- [ ] Bộ 10 câu nhân viên mẫu có nhiều số — tóm tắt không sai con số nào.
- [ ] Prompt lọc nhiễu, thử trong môi trường ồn.
- [ ] Bộ test + kết quả đo theo tiêu chí mục 6 `luong-xu-ly-chinh.md`.

---

## 6. TV4 — Backend

- [ ] Thêm `spring-boot-starter-web` vào `pom.xml`.
- [ ] 4 endpoint **giả** trả JSON mẫu theo mục 4 `luong-xu-ly-chinh.md` — **trước mốc 0:30**.
- [ ] Validate request: enum `context`, số frame, dung lượng file.
- [ ] Cấu hình multipart (`max-file-size`, `max-request-size`).
- [ ] Response lỗi chung `{ error: { code, message } }` với đủ 7 mã lỗi.
- [ ] `AiGateway` bản mock + bản thật theo mục 4.6 `luong-xu-ly-chinh.md`; API key đọc từ biến môi trường.
- [ ] Kiểm tra output AI sau khi nhận: schema, ép `glosses` về bộ ký hiệu (mục 7.4 `luong-xu-ly-chinh.md`), `highlights` có trong `summary`.
- [ ] Ghép prompt của TV3; timeout → `504 AI_TIMEOUT`; sai schema → `502 AI_UPSTREAM_ERROR`.
- [ ] Backend chạy ở nơi đã chốt, mobile gọi được từ điện thoại thật.
- [ ] `./mvnw test` pass; không có API key trong code/commit.
- [ ] Test end-to-end: hội thoại 3 lượt < 30 giây, số liệu tóm tắt đúng.

---

## 7. Cần chốt ngay đầu giờ

- [ ] Nhà cung cấp LLM vision / LLM text / STT.
- [ ] Backend chạy ở đâu (laptop cùng wifi hay server).
- [ ] Bộ ký hiệu (đề xuất 20 ký hiệu ở mục 7 `luong-xu-ly-chinh.md`).
- [ ] Ngưỡng `confidence` (đề xuất 0.7).
