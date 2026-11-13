# SignBridge Backend (TV4)

Spring Boot 4.1 · Java 21+. Đặc tả API: `../docs/luong-xu-ly-chinh.md` mục 4.

## Chạy

```bash
./mvnw spring-boot:run          # cổng 8080, ai.mode=mock (trả JSON mẫu)
./mvnw test
```

Mobile gọi từ điện thoại cùng wifi: `http://<IP-laptop>:8080/api/...` (xem IP bằng `hostname -I`).

## Endpoint

| Method | Path | Body |
|---|---|---|
| GET | `/api/health` | — |
| POST | `/api/sign` | multipart: `context`, `frames` (4/8/12/16 file JPEG ≤ 250KB), `personalChips` (JSON array), `previousIncoming` |
| POST | `/api/expand` | JSON: `{context, chips[1..5], previousIncoming}` |
| POST | `/api/summarize` | multipart: `context`, `audio` (m4a ≤ 2MB), `previousOutgoing` |

Chế độ mock: gửi `personalChips=["MOCK_LOW"]` lên `/api/sign` để thử luồng confidence thấp
(`glosses` có `UNKNOWN`, `spoken_sentence` rỗng).

## Cấu trúc

```
api/           ApiController (4 endpoint + validate request), ExpandRequest
conversation/  ConversationService (kiểm tra output AI — mục 4.6, 7.4), SignVocabulary (20 ký hiệu)
ai/            AiGateway + MockAiGateway, các record input/output AI
common/        ContextType, ApiException, GlobalExceptionHandler (response lỗi chung)
```

## Cấu hình (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `AI_MODE` | `mock` | `mock` hoặc `real` (chưa có RealAiGateway) |
| `AI_STT_BASE_URL` | `http://localhost:8000` | Service STT của TV3 |

Không commit API key — chỉ đọc từ biến môi trường.
