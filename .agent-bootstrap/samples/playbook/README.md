# Playbook: <tên> — Mẫu 4 lớp

> Playbook = một quy trình phát triển (TDD, BDD, trunk-based…) đóng gói thành **một thư mục 4 lớp**,
> bật/tắt nguyên khối bằng cấu hình. Rút từ playbook TDD của repo mẫu.

## Cấu trúc

```text
<thư mục playbook>/<tên>/
├── README.md                    # file này
├── knowledge/guide.md           # Lớp 1 — tại sao + làm thế nào
├── skills/workflow.md           # Lớp 2 — tự kích hoạt đúng quy trình
├── hooks/guard.js               # Lớp 3 — nhắc/chặn khi vi phạm
└── verification/compliance.md   # Lớp 4 — đo mức độ áp dụng
```

| Lớp | Vai trò | Thiếu lớp này thì sao |
|---|---|---|
| **Knowledge** | Agent hiểu "tại sao" và "làm thế nào" | Biết phải làm nhưng làm sai cách |
| **Skill** | Tự hành động đúng quy trình khi có trigger | Dev phải nhớ gọi, dễ quên |
| **Hook** | Nhắc/chặn khi không tuân thủ | Agent và dev có thể bỏ qua |
| **Verification** | Đo compliance từ log/CI | Không biết đội có thực sự làm không |

## Bật / tắt

```json
"playbooks": {
  "<tên>": { "enabled": true, "enforcement": "monitor-only" }
}
```

- **Một nơi duy nhất** để bật/tắt. Agent chỉ áp dụng playbook `enabled: true`.
- Hook **tự đọc** cờ này lúc chạy → enforcement là điều kiện thật ở runtime, không chỉ là chỉ dẫn.
- [Unverified] Repo mẫu đặt khối `playbooks` trong `.claude/settings.json`; chưa xác minh harness bỏ qua hay
  cảnh báo key tự đặt — cân nhắc file cấu hình riêng nếu schema harness đích chặt.

## Mức enforcement (tiệm tiến)

```text
monitor-only  →  warn  →  block
(chỉ đo)         (nhắc)    (chặn: stderr + exit 2)
```

1. Bật mới ở `monitor-only`, hook chỉ ghi log JSONL (vd `.claude/logs/playbook-<tên>.jsonl`).
2. Sau khi có baseline (vd 2 sprint) → `warn`.
3. Ổn định → `block`.

## Lớp hook — yêu cầu

- Theo giao ước exit code ở `../hooks/README.md`; `block` dùng `stderr` + `exit 2`, `warn` dùng `exit 0`.
- Cấu hình thiếu/hỏng → coi như tắt; lỗi nội bộ → fail-open.
- Bản ghi log tối thiểu: `{ts, playbook, enforcement, tool, file, compliant}` — không ghi nội dung file.

## Lớp verification — mẫu metric

- **Compliance rate** = % MR tuân thủ / tổng MR.
- **Guard violation count** = số bản ghi `compliant:false` / tuần.
- Nguồn: log JSONL của hook + diff MR + báo cáo CI.

## Khi nào áp dụng / không áp dụng

- Áp dụng: <loại thay đổi>.
- Không bắt buộc: thay đổi thuần config, tài liệu, spike/prototype bỏ đi.
