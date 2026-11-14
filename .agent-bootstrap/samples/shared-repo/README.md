# Mô hình repo dùng chung (chuẩn tổ chức cho nhiều repo)

> Dùng khi nhiều repo cần **cùng** bộ agent/skill/hook/knowledge (mức `full`, `adoption-tiers.md`).
> Rút từ repo mẫu — tên thư mục, lệnh sync dưới đây là **khung**; repo đích chọn cơ chế phân phối của mình
> (git submodule, package nội bộ, script copy…). Không tạo repo dùng chung trong lượt bootstrap — chỉ đề xuất.

## 1. Bố cục

```text
<shared-repo>/                        # repo trung tâm — nguồn sự thật
├── HUB-COMMON.md                     # hub org-owned → sync đổi tên thành hub của repo đích, GHI ĐÈ
├── ROUTING-COMMON.md                 # routing org-owned → sync thành <AGENT_DIR>/AGENTS.md, GHI ĐÈ
├── agents/  skills/  commands/       # sync COPY vào <AGENT_DIR>/ của repo đích
├── hooks/                            # KHÔNG copy — cấu hình hook của repo đích trỏ thẳng vào đây
│   ├── lib/                          # module dùng chung (vd luật secret, tìm gốc project)
│   └── package.json                  # {"type":"commonjs"} nếu hook viết Node
├── knowledge/
│   ├── org/{<tầng>,shared}/          # convention, security, git workflow, chuẩn thiết kế, phi chức năng
│   ├── playbooks/{_template,<tên>}/  # playbook 4 lớp
│   └── decisions/                    # ADR cấp tổ chức (hiếm)
└── ci/check-structure.*              # CI: kiểm file lõi còn đủ (sync phụ thuộc vào chúng)
```

Repo đích:

```text
<repo>/
├── <hub>                    # ← sinh từ HUB-COMMON.md (KHÔNG sửa tay)
├── <AGENT_DIR>/AGENTS.md    # ← sinh từ ROUTING-COMMON.md (KHÔNG sửa tay)
├── <AGENT_DIR>/{agents,skills,commands}/   # ← copy từ shared repo
├── <KNOWLEDGE_DIR>/CLAUDE.md               # KÊNH TUỲ BIẾN DUY NHẤT của repo — hub @ file này
└── <shared-repo>/                          # submodule / package
```

## 2. Quy tắc sở hữu

| Loại file | Sửa ở đâu | Cơ chế đến repo đích |
|---|---|---|
| Hub, routing | Shared repo (qua MR) | Sync **đổi tên + ghi đè** — sửa tay ở repo đích sẽ mất |
| Agent, skill, command | Shared repo (qua MR) | Sync **copy, ghi đè** |
| Hook | Shared repo (qua MR) | **Trỏ thẳng** — bump phiên bản shared repo là đủ |
| Knowledge org | Shared repo (qua MR) | Đọc trực tiếp từ shared repo |
| Kiến thức / tuỳ biến dự án | `<KNOWLEDGE_DIR>/` của repo đích | — |

- Ưu tiên: **dự án > tổ chức**. Dự án ghi đè → khai báo rõ ở `architecture.md` mục "Quy ước đặc thù (ghi đè)".
- Hub **không** `@import` agent/skill (harness tự phát hiện) — chỉ giữ **bảng trỏ**, thêm/đổi tên thì cập nhật bảng.
- Hub chỉ `@` file cần ở **mọi** phiên; còn lại liệt kê "đọc khi cần".

## 3. Vòng cập nhật

```text
MR vào shared repo ──► CI (lint + check-structure) ──► merge
   ──► tech lead chạy sync cho các repo đích (cập nhật phiên bản shared repo + copy/ghi đè)
   ──► review diff ──► commit con trỏ phiên bản + file đã sync trong từng repo (qua MR repo đó)
```

- Script sync **không tự commit**; bỏ qua repo có thay đổi dở.
- Thêm playbook: copy `playbooks/_template/` → điền 4 lớp → MR → bật `monitor-only` ở repo đích.

## 4. Bẫy đã gặp

- Sửa tay hub/routing ở repo đích → mất ở lần sync sau. Agent phát hiện nhu cầu sửa → **đề xuất MR sang shared repo** (skill `workflow-adapt`).
- Submodule chưa init → hook trỏ vào submodule báo `module not found` hoặc im lặng; ghi điều kiện này vào tài liệu hook.
- Bản sao skill trong repo đích lệch nguồn (do sửa tay) → so sánh với nguồn khi rà hạ tầng (Bước 4 của prompt: mục "trùng-lệch").
