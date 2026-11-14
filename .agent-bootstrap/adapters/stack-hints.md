# Gợi ý nhận diện stack

> Bảng dưới chỉ là **ứng viên** để biết tìm ở đâu. Lệnh chỉ được ghi vào hồ sơ dự án khi đã
> **xác nhận từ file của repo** (manifest, script, README, CI). Lệnh suy luận → đánh dấu `[suy luận]`.
> Không chạy lệnh cần mạng, credential, DB hay chạy lâu để "thử".

## 1. Manifest → nơi tìm lệnh

| Dấu hiệu | Stack | Tìm lệnh build/test ở đâu | Ứng viên thường gặp |
|---|---|---|---|
| `pom.xml`, `mvnw` | Java/Kotlin – Maven | `pom.xml` (plugin surefire/failsafe), README, CI | `./mvnw test`, `mvn test` |
| `build.gradle(.kts)`, `gradlew` | JVM – Gradle | `build.gradle`, README, CI | `./gradlew test` |
| `package.json` + lockfile | JS/TS | `scripts` trong `package.json`; lockfile quyết định trình quản lý gói | `npm test`, `pnpm test`, `yarn test` |
| `pyproject.toml`, `setup.cfg`, `requirements*.txt`, `tox.ini` | Python | `[tool.pytest]`, `tox.ini`, `noxfile.py`, `Makefile`, CI | `pytest`, `tox` |
| `go.mod` | Go | `Makefile`, CI | `go test ./...` |
| `Cargo.toml` | Rust | `Cargo.toml`, CI | `cargo test` |
| `*.sln`, `*.csproj` | .NET | CI, README | `dotnet test` |
| `composer.json` | PHP | `scripts` trong `composer.json` | `composer test`, `vendor/bin/phpunit` |
| `Gemfile` | Ruby | `Rakefile`, CI | `bundle exec rspec`, `rake test` |
| `pubspec.yaml` | Dart/Flutter | README, CI | `flutter test` |
| `*.tf` | Terraform | CI, README | `terraform validate` (không `apply`) |
| `Dockerfile`, `docker-compose*.yml` | Container | CI | — (chỉ đọc, không build/up khi chưa duyệt) |
| `Makefile`, `justfile`, `Taskfile.yml` | Bất kỳ | Target `test`/`lint`/`build` | `make test` |

## 2. Nhận diện tầng (layer)

| Dấu hiệu | Tầng gợi ý |
|---|---|
| Controller/route/handler, ORM/entity, migration | `backend` |
| Component/page/view, CSS, bundler config (Vite/Webpack/Next) | `frontend` |
| Notebook, DAG (Airflow/dbt), SQL transform | `data` |
| IaC, Helm chart, pipeline deploy | `infra` |
| Android/iOS project, React Native/Flutter | `mobile` |

Repo nhiều tầng/monorepo → map **theo thư mục** vào mục 4 của hồ sơ (mỗi tầng một dòng), không gộp thành một giả định.

## 3. CI

| Dấu hiệu | Nền tảng |
|---|---|
| `.gitlab-ci.yml` | GitLab CI |
| `.github/workflows/*.yml` | GitHub Actions |
| `azure-pipelines.yml` | Azure Pipelines |
| `Jenkinsfile` | Jenkins |
| `bitbucket-pipelines.yml` | Bitbucket Pipelines |

Không thấy file CI ≠ không có CI (có thể cấu hình ngoài repo) → ghi `"không thấy trong repo"`.

## 4. Runtime cho hook

| Có sẵn trong repo/dev env | Chọn |
|---|---|
| `package.json` hoặc team đã dùng Node | `node` (viết theo `samples/hooks/README.md`) |
| Repo Python, không có Node | `python` (viết theo `samples/hooks/README.md`) |
| Không chắc runtime có trên mọi máy dev | Ưu tiên git hook + CI; hook harness để tuỳ chọn, ghi điều kiện chạy |

## 5. Quy ước vị trí test (cho cổng test và guard của playbook)

> Xác nhận bằng **file test có thật** trong repo — bảng chỉ là ứng viên.

| Stack | Ứng viên file test cho `X` |
|---|---|
| Java/Kotlin (Maven/Gradle) | `src/main/<pkg>/X.java` → `src/test/<pkg>/XTest.java` (hoặc `XIT` cho integration) |
| JS/TS | `X.test.ts` / `X.spec.ts` cùng thư mục, hoặc `__tests__/X.test.ts` |
| Python | `tests/test_x.py`, hoặc `x_test.py` |
| Go | `x_test.go` cùng package |
| .NET | project `*.Tests` song song |
| Ruby | `spec/<path>/x_spec.rb` |

Repo nhiều module → ánh xạ **theo từng module** (vd `<module>/src/main` → `<module>/src/test`).

## 6. Tín hiệu cho bản đồ thích ứng

| Cần biết | Tìm ở đâu |
|---|---|
| Có DB/ORM? | Dependency ORM/driver trong manifest, cấu hình datasource (chỉ đọc **tên key**), thư mục migration |
| Có migration framework? | Thư mục `db/migration`, `migrations/`, `alembic/`, `prisma/migrations`… |
| Có quy trình thiết kế? | Thư mục spec/design/ADR trong repo hoặc knowledge dùng chung; hỏi người dùng nếu không thấy |
| Có thư viện dùng chung nội bộ? | Group/scope nội bộ trong manifest (không suy từ tài liệu) |
| Có nguồn tra cứu ngoài? | Cấu hình MCP project (`.mcp.json`…), tài liệu đội; scope người dùng → hỏi người dùng |
| Quy ước commit thực tế | `git log --oneline -20` (chỉ đọc) |

Áp dụng tín hiệu theo `adaptation-rules.md` §2.
