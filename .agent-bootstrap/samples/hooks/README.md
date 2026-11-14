# Hướng dẫn viết hook an toàn

> Hướng dẫn để agent **tự viết** hook trong runtime phù hợp với repo đích (theo `hook_runtime` trong
> hồ sơ dự án). Không có file code mẫu đi kèm — agent sinh code từ đặc tả dưới đây, rồi test bằng bảng fixture.
> Chỉ tạo hook khi harness hỗ trợ (xem `../../adapters/harness-matrix.md`) **và** người dùng đã duyệt.
> Harness không có hook → dùng git hook (`pre-commit`) + CI cho phần cần ép buộc, còn lại là checklist.

## 1. Giao ước exit code (Claude Code — harness khác phải xác minh tương đương)

| Exit code | Hành vi harness |
|---|---|
| `0` | Cho qua; output không hiện cho model — **trừ `SessionStart`**: `stdout` được nạp vào context (JSON: `hookSpecificOutput.additionalContext` vào context của model, `systemMessage` hiện cho người dùng) |
| `2` | **Chặn**; nội dung `stderr` được feed lại cho model để tự sửa |
| khác `0` (vd `1`) | Lỗi **không chặn** — chỉ hiện `stderr` cho người dùng, tool **VẪN chạy** |

> **MUST** chặn bằng `stderr` + `exit 2`. **NEVER** chặn bằng `stdout` + `exit 1` — thông báo vẫn in ra nhưng
> lệnh nguy hiểm vẫn thực thi (đã xảy ra thật ở repo mẫu). Chạy tay script thấy "đúng" chưa đủ —
> **phải kiểm chứng trong một phiên harness thật**.

## 2. Đầu vào hook (Claude Code)

Hook nhận một JSON qua `stdin`, các trường dùng tới:

| Trường | Ý nghĩa |
|---|---|
| `tool_name` | Tên tool (`Bash`, `Write`, `Edit`…) |
| `tool_input.command` | Lệnh shell khi `tool_name = Bash` |
| `tool_input.file_path`, `tool_input.content`, `tool_input.new_string` | Khi ghi/sửa file |
| `cwd` | Thư mục làm việc tại thời điểm gọi (có thể là thư mục con) |

> Harness khác: xác minh định dạng payload trước khi viết.

## 3. Đặc tả hook mẫu `pre-tool-use-guard` (chặn lệnh Bash nguy hiểm)

**Event:** `PreToolUse`, matcher `Bash`. **Hành vi:** đọc `tool_input.command`, tách theo `\n | ; &`, áp các luật sau:

1. **Force push vào nhánh được bảo vệ** (`git.protected_branches` trong hồ sơ, mặc định `main`, `master`):
   cùng một đoạn lệnh có `git push`, cờ `--force` hoặc `-f`, và tên nhánh được bảo vệ — **bất kể thứ tự** cờ/nhánh.
   Không chặn force push vào nhánh khác.
2. **`rm` đệ quy/cưỡng bức nhắm vào path nguy hiểm:** có cờ chứa `r`/`R`/`f`/`F` (kể cả tách rời `-r -f`) hoặc
   `--recursive`/`--force`, **và** target là một trong: `/` hoặc path tuyệt đối POSIX · ổ đĩa Windows (`D:/`, `D:\`) ·
   UNC (`\\server\share`) · `~` · `$HOME`/`${HOME}` · `.` hoặc `./` · `*` hoặc `./*`.
   **Cho phép** target tương đối có tên (`rm -rf build`).
3. **`TRUNCATE TABLE`** (không phân biệt hoa thường).
4. **`DROP TABLE` / `DROP DATABASE` / `DROP SCHEMA`** không kèm `IF EXISTS`.

**Khi khớp:** ghi ra `stderr` một dòng `🚫 Đã chặn bởi <tên hook>: <tên luật>.` + dòng `Cách xử lý: <gợi ý>`, rồi `exit 2`.
**Khi không khớp / tool khác Bash:** `exit 0`.

### Khung xử lý (pseudocode — viết lại bằng runtime của repo)

```text
đọc toàn bộ stdin
nếu không parse được JSON  → exit 0          # fail-open
thử:
    nếu tool_name == "Bash":
        luật = tìm_luật_khớp(tool_input.command)
        nếu có luật:
            ghi stderr "🚫 Đã chặn bởi …: <tên luật>.\n  Cách xử lý: <gợi ý>"
            exit 2
ngoại lệ bất kỳ → exit 0                     # fail-open
exit 0
```

## 4. Quy tắc viết hook (mọi runtime)

1. **Đường dẫn trong cấu hình hook:** dùng biến gốc project của harness (Claude Code: `"${CLAUDE_PROJECT_DIR:-.}/<HOOKS_DIR>/<file>"`) — không dùng `./`.
2. **Gốc project trong hook:** biến môi trường của harness → trường `cwd` trong payload → suy từ vị trí file hook → thư mục hiện tại. Không lấy thư mục hiện tại làm nguồn chính (sau một lệnh `cd`, hook có thể chạy ở thư mục con).
3. **Fail-open:** input hỏng / lỗi nội bộ → `exit 0`. Hook ghi log không bao giờ chặn.
4. **Một nguồn luật:** luật dùng chung giữa hook harness và git `pre-commit` (vd quét secret) đặt trong **một** module; không giữ hai bản song song.
5. **Giảm chặn nhầm:** phân luật theo loại file (code/tài liệu chỉ soi string literal; config soi cả giá trị trần), chấp nhận placeholder (`${VAR}`, `<PLACEHOLDER>`), có escape hatch theo dòng thấy được khi review, **che giá trị** khi in.
6. **Node:** viết CommonJS và đặt `package.json` `{"type":"commonjs"}` cạnh thư mục hook (tránh vỡ khi repo host dùng ESM). **Python:** chỉ dùng thư viện chuẩn, ghi `stderr` bằng UTF-8.
7. **Thông báo** viết tiếng Việt; tên luật, lệnh, path giữ nguyên.
8. **Log tối thiểu:** cắt độ dài, redact secret, thư mục log nằm trong `.gitignore`, có thời gian lưu.
9. Hook có thể chặn: bật mới ở mức nhắc/quan sát khi độ chính xác chưa được chứng minh.

## 5. Khi hook không chạy — kiểm theo thứ tự

| # | Điều kiện | Cách xử lý |
|---|---|---|
| 1 | Harness phải mở **tại gốc repo** (mở ở thư mục con có thể không nạp cấu hình ở gốc) | Mở lại tại gốc |
| 2 | Runtime của hook (`node` / `python`) có trên PATH | Cài runtime hoặc đổi `hook_runtime` |
| 3 | Submodule chứa hook đã init (nếu hook nằm trong submodule) | `git submodule update --init <submodule>` |
| 4 | Workspace đã được **trust** (Claude Code: thư mục chưa chấp nhận hộp thoại trust → hook trong cấu hình chia sẻ không chạy, chỉ thấy dòng cảnh báo bỏ qua cấu hình) | Mở harness tương tác tại gốc repo một lần và chấp nhận trust |

> Triệu chứng chung của cả 4 điều kiện: hook **im lặng** hoặc chỉ một dòng `hook error` mờ — dễ tưởng hook đang bảo vệ trong khi không.

## 6. Git hook không tự theo clone

`git config core.hooksPath` nằm trong `.git/config` — không được version-control, nên clone mới mất git hook.
Có thể dùng một hook đầu phiên (Claude Code: `SessionStart`) chỉ đặt lại giá trị này: im lặng khi đã đúng,
luôn `exit 0`, cảnh báo nếu submodule chưa init. Đổi git config là **cấu hình đang hoạt động → cần duyệt**.

## 7. Bảng fixture bắt buộc

Tạo file JSON payload ở **thư mục tạm** (không gõ lệnh nguy hiểm trực tiếp trên command line — hook đang chạy
có thể chặn chính lệnh test), đưa vào `stdin` của hook, so `exit code`:

| # | `tool_name` | `command` | Kỳ vọng |
|---|---|---|---|
| 1 | Bash | `git status` | `0` |
| 2 | Bash | `git push --force origin main` | `2` |
| 3 | Bash | `git push origin master -f` | `2` |
| 4 | Bash | `git push --force origin feature/abc` | `0` |
| 5 | Bash | `rm -rf build` | `0` |
| 6 | Bash | `rm -rf /var/data` | `2` |
| 7 | Bash | `rm -rf D:/WORKSPACE/x` | `2` |
| 8 | Bash | `rm -rf \\server\share` | `2` |
| 9 | Bash | `rm -r -f ~` | `2` |
| 10 | Bash | `rm -rf .` | `2` |
| 11 | Bash | `rm -rf ./*` | `2` |
| 12 | Bash | `rm /tmp/a.txt` | `0` |
| 13 | Bash | `echo 'TRUNCATE TABLE t'` | `2` |
| 14 | Bash | `echo 'DROP TABLE IF EXISTS t'` | `0` |
| 15 | Bash | `echo 'DROP TABLE t'` | `2` |
| 16 | Write | (bất kỳ) | `0` |
| 17 | — | stdin không phải JSON | `0` |

Sau khi fixture PASS hết → kiểm chứng ít nhất ca #2 và #6 **trong phiên harness thật** (trên repo/fixture an toàn),
xác nhận lệnh bị chặn thật chứ không chỉ in cảnh báo.

## 8. Hook đầu phiên (`SessionStart`) — chỉ nhắc, không chặn

Hai mẫu hữu ích, cùng khung: **kiểm offline → đủ thì im lặng → thiếu thì nhắc → luôn `exit 0`**.

| Hook | Kiểm gì | Khi thiếu |
|---|---|---|
| `ensure-git-hooks` | `git config core.hooksPath` đúng thư mục git hook của repo (§6) | Đặt lại giá trị (cần duyệt khi cài lần đầu); submodule chưa init → cảnh báo |
| `ensure-external-tools` | Nguồn tra cứu ngoài bắt buộc (vd MCP server) **đã đăng ký** theo một manifest máy đọc; biến môi trường cần thiết **có được đặt** (chỉ kiểm có/không, không in giá trị) | In nhắc cài: `systemMessage` cho người dùng + `additionalContext` cho model (để model biết phần nào chưa tra được) |

- Matcher gợi ý: `startup|resume|clear`.
- Danh sách nguồn bắt buộc đặt trong **manifest** (JSON, không chứa URL/token) — thêm/bớt nguồn sửa manifest, không sửa hook.
- Không kiểm kết nối mạng (chậm, phụ thuộc VPN) — ca đó model xử lý theo `samples/knowledge/external-knowledge.md`.
- File cấu hình người dùng hỏng/không đọc được → im lặng (không báo động giả).

## 9. Hook ghi log (`PostToolUse`, matcher `.*`)

- Mỗi tool call một dòng JSONL: `{ts, tool, session (cắt ngắn), input (tóm tắt), output (tóm tắt)}`.
- Tóm tắt theo tool: lệnh shell, đường dẫn file, pattern — **không** ghi nội dung file.
- Cắt độ dài (vd 200 ký tự) **và** redact mẫu secret trước khi ghi.
- Đường dẫn log tính **sau** khi đọc payload (gốc project theo §4.2); thư mục log nằm trong `.gitignore`.
- Mọi lỗi → nuốt, `exit 0`. Logger **không bao giờ** chặn.
- Đặt thời gian lưu / xoay vòng log; ghi rõ trong tài liệu ai được đọc log.

## 10. Luật quét secret dùng chung (hook harness + git `pre-commit`)

Một module, hai nơi gọi (hook harness `require`/import trực tiếp; `pre-commit` gọi qua CLI `--file <path>`).
**Sửa luật chỉ ở module này.**

| Tầng | Luật | Áp cho |
|---|---|---|
| 1 | Token có tiền tố nhà cung cấp (vd `sk-…`, `AKIA…`, `ghp_…`, `AIza…`), khối PEM private key, credential trong connection URL. Tiền tố phải có **ranh giới đầu từ** (vd `(?<![A-Za-z0-9])`) — thiếu thì `task-…`, `risk-…`, `disk-…` khớp `sk-` và bị chặn oan | Mọi loại file |
| 2 | Cặp `key nhạy cảm = value`, phán theo **loại file × hình dạng value**: code → chỉ string literal có nháy; tài liệu → literal `"`/`'` (backtick là code-span); config (`.env`, `.yml`, `.json`, `.properties`, không đuôi) → cả bare lẫn quoted | Theo loại file |
| 3 | Escape hatch theo dòng (vd comment `allow-secret`) — thấy được khi review | Mọi loại file |

Value **an toàn** (không chặn): `${VAR}`, `${VAR:-default}` (shell fallback), `$VAR`, `$(cmd)`, `<PLACEHOLDER>`, `{{template}}`, boolean/`null`, tên kiểu dữ liệu (`string`, `number`…), độ dài < 4.
Lưu ý: cú pháp `${VAR:default}` của một số framework **chứa giá trị hardcode** sau dấu `:` → vẫn chặn.
Khi in giá trị bị chặn → **che bớt** (vd `abcd***(N ký tự)`).

Môi trường thiếu runtime / thiếu submodule → `pre-commit` **cảnh báo rồi cho commit** (không chặn vì lý do môi trường); ghi rõ hạn chế này.

Fixture tối thiểu (tạo file trong thư mục tạm, dùng **giá trị giả** có hình dạng giống secret — KHÔNG dùng secret thật):

| # | Loại file | Dòng | Kỳ vọng |
|---|---|---|---|
| S1 | config | `password=<giá trị giả ≥ 8 ký tự>` | chặn |
| S2 | config | `password=${DB_PASSWORD}` | cho qua |
| S3 | code | `const token = response.data.token` | cho qua |
| S4 | code | `String password = "<giá trị giả>";` | chặn |
| S5 | code | `const taskController = 'task-management'` | cho qua (ranh giới tiền tố) |
| S6 | tài liệu | `` `password: <giá trị giả>` `` (code-span) | cho qua |
| S7 | config | `<giá trị giả> # allow-secret` | cho qua |

## 11. Hook của playbook (vd guard TDD, `PostToolUse` matcher `Write|Edit`)

- Đọc `enabled`/`enforcement` từ file cấu hình **lúc chạy**; thiếu/hỏng → coi như tắt.
- Chỉ xét file **implementation** (đuôi code, nằm trong thư mục source, không phải file test).
- Sinh danh sách ứng viên file test theo **quy ước thật của repo** (mục 4 hồ sơ — vd `src/main/` → `src/test/` + hậu tố `Test`; `foo.ts` → `foo.test.ts`/`__tests__/`; `foo.py` → `test_foo.py`). Repo dùng quy ước khác → sửa ánh xạ trước khi bật.
- `monitor-only` → chỉ ghi log `{ts, playbook, enforcement, tool, file, compliant}`; `warn` → nhắc, `exit 0`; `block` → `stderr` + `exit 2`.
- Fixture: file source có test (cho qua) · file source thiếu test (log/nhắc/chặn theo mức) · chính file test (cho qua) · file không phải code (cho qua) · cấu hình playbook tắt (cho qua).
