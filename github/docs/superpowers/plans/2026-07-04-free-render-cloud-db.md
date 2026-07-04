# Free Render Cloud Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DSA deployable on Render free while storing durable app data in a free external Postgres database such as Neon or Supabase.

**Architecture:** Keep Render as the free web host and move durable state from local SQLite files to a cloud Postgres connection supplied through `DATABASE_URL`. SQLite remains the local desktop default. Render secrets stay in environment variables and are never committed.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, SQLite for local, Postgres via `psycopg[binary]`, Render Blueprint.

## Global Constraints

- Do not delete files without explicit user confirmation.
- The app must keep working locally with `DATABASE_PATH=./data/stock_analysis.db`.
- Cloud deploy must prefer `DATABASE_URL` when it is set.
- API keys and model keys must be `sync: false` in Render and must not be committed.
- `ADMIN_AUTH_ENABLED=true` must be enabled for public cloud deploys.
- Free Render filesystem must not be treated as durable storage.

---

### Task 1: Add Database URL Configuration

**Files:**
- Modify: `D:\codex项目文件\gitup\github\src\config.py`
- Modify: `D:\codex项目文件\gitup\github\.env.example`
- Test: `D:\codex项目文件\gitup\github\tests\test_config_env_compat.py`

**Interfaces:**
- Produces: `Config.database_url: Optional[str]`
- Produces: `Config.get_db_url() -> str`, returning `DATABASE_URL` when present, otherwise local SQLite URL.

- [ ] **Step 1: Write the failing test**

Add this test to `tests/test_config_env_compat.py`:

```python
    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_database_url_takes_precedence_over_database_path(
        self,
        _mock_parse_litellm_yaml,
        _mock_setup_env,
    ):
        with patch.dict(
            os.environ,
            {
                "STOCK_LIST": "600519",
                "DATABASE_URL": "postgresql+psycopg://user:pass@db.example/dsa",
                "DATABASE_PATH": "./data/should_not_be_used.db",
            },
            clear=True,
        ):
            config = Config._load_from_env()

        self.assertEqual(config.database_url, "postgresql+psycopg://user:pass@db.example/dsa")
        self.assertEqual(config.get_db_url(), "postgresql+psycopg://user:pass@db.example/dsa")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_config_env_compat.py::ConfigEnvCompatibilityTestCase::test_database_url_takes_precedence_over_database_path -q
```

Expected: fails because `Config.database_url` does not exist or `get_db_url()` ignores `DATABASE_URL`.

- [ ] **Step 3: Add configuration support**

In `src/config.py`, add `database_url: Optional[str] = None` to `Config`, load `DATABASE_URL` in `_load_from_env()`, and update `get_db_url()`:

```python
    def get_db_url(self) -> str:
        database_url = (self.database_url or "").strip()
        if database_url:
            return database_url

        db_path = Path(self.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.absolute()}"
```

Add this to `.env.example` near `DATABASE_PATH`:

```dotenv
# Cloud deployment: set DATABASE_URL to a durable Postgres URL from Neon/Supabase.
# When DATABASE_URL is set, it takes precedence over DATABASE_PATH.
# DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname?sslmode=require
```

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command. Expected: pass.

---

### Task 2: Add Postgres Driver and Cloud-Safe Engine Handling

**Files:**
- Modify: `D:\codex项目文件\gitup\github\requirements.txt`
- Modify: `D:\codex项目文件\gitup\github\src\storage.py`
- Test: `D:\codex项目文件\gitup\github\tests\test_storage.py`

**Interfaces:**
- Produces: Postgres-capable SQLAlchemy URL support through `postgresql+psycopg://...`.
- Produces: non-SQLite write path remains generic SQLAlchemy ORM.

- [ ] **Step 1: Write the failing tests**

Add tests to `tests/test_storage.py`:

```python
    def test_database_manager_marks_postgres_like_url_as_non_sqlite(self):
        DatabaseManager.reset_instance()
        Config.reset_instance()

        with patch("src.storage.create_engine") as mock_create_engine:
            mock_engine = mock_create_engine.return_value
            mock_engine.url.get_backend_name.return_value = "postgresql"
            with patch.object(Base.metadata, "create_all"):
                with patch.object(DatabaseManager, "_ensure_llm_usage_telemetry_columns"):
                    with patch.object(DatabaseManager, "_ensure_intelligence_item_scope_values"):
                        with patch.object(DatabaseManager, "_ensure_schema_migration_record"):
                            with patch.object(DatabaseManager, "_ensure_intelligence_items_unique_index"):
                                db = DatabaseManager(db_url="postgresql+psycopg://u:p@h:5432/dsa")

        self.assertFalse(db._is_sqlite_engine)
        DatabaseManager.reset_instance()

    def test_requirements_include_psycopg_driver(self):
        requirements = Path(__file__).resolve().parents[1].joinpath("requirements.txt").read_text(encoding="utf-8")
        self.assertIn("psycopg[binary]", requirements)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_storage.py::StorageTestCase::test_requirements_include_psycopg_driver tests/test_storage.py::StorageTestCase::test_database_manager_marks_postgres_like_url_as_non_sqlite -q
```

Expected: driver test fails until requirements are updated.

- [ ] **Step 3: Add driver dependency**

Add to `requirements.txt` under database dependencies:

```text
psycopg[binary]>=3.2.0       # PostgreSQL driver for Render + Neon/Supabase cloud deployments
```

- [ ] **Step 4: Run tests to verify they pass**

Run the same pytest command. Expected: pass.

---

### Task 3: Move Render Blueprint to the Git Repo Root for GitHub Deployment

**Files:**
- Create or modify: `D:\codex项目文件\gitup\github\render.yaml`
- Modify: `D:\codex项目文件\gitup\github\docs\deploy-render-free-postgres.md`

**Interfaces:**
- Produces: Render Blueprint at the repository root that Render can read from `kaikai123421/codex`.
- Consumes: `DATABASE_URL` from Neon/Supabase, marked `sync: false`.

- [ ] **Step 1: Create `github/render.yaml`**

Use this content:

```yaml
services:
  - type: web
    name: dsa-private
    runtime: docker
    plan: free
    region: singapore
    branch: main
    dockerfilePath: docker/Dockerfile
    dockerContext: .
    dockerCommand: python main.py --serve-only --host 0.0.0.0 --port 8000
    healthCheckPath: /api/v1/health
    autoDeployTrigger: commit
    envVars:
      - key: TZ
        value: Asia/Shanghai
      - key: PYTHONUNBUFFERED
        value: "1"
      - key: WEBUI_HOST
        value: 0.0.0.0
      - key: WEBUI_PORT
        value: "8000"
      - key: API_PORT
        value: "8000"
      - key: PORT
        value: "8000"
      - key: WEBUI_AUTO_BUILD
        value: "false"
      - key: ADMIN_AUTH_ENABLED
        value: "true"
      - key: ADMIN_SESSION_MAX_AGE_HOURS
        value: "24"
      - key: DATABASE_URL
        sync: false
      - key: LOG_DIR
        value: /app/logs
      - key: CORS_ALLOW_ALL
        value: "false"
      - key: TRUST_X_FORWARDED_FOR
        value: "true"
      - key: STOCK_LIST
        value: 000725,515880,515050,601138,300502,159732
      - key: REPORT_LANGUAGE
        value: zh
      - key: SCHEDULE_ENABLED
        value: "false"
      - key: DEEPSEEK_API_KEY
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: OPENAI_API_KEY
        sync: false
      - key: TUSHARE_TOKEN
        sync: false
      - key: FINNHUB_API_KEY
        sync: false
      - key: BRAVE_API_KEYS
        sync: false
```

- [ ] **Step 2: Add deployment guide**

Create `docs/deploy-render-free-postgres.md` with exact user steps:

```markdown
# Render Free + Neon/Supabase Free Deployment

This setup runs the DSA web app on Render free and stores durable data in a free Postgres database.

## 1. Create a free cloud database

Use Neon or Supabase and create a Postgres project. Copy the pooled connection string and convert it to SQLAlchemy format:

```text
postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require
```

## 2. Deploy on Render

Open:

```text
https://dashboard.render.com/blueprint/new?repo=https://github.com/kaikai123421/codex
```

Select the `render.yaml` blueprint from the repo root.

## 3. Fill Render environment secrets

Required:

- `DATABASE_URL`: the Neon/Supabase connection string.
- At least one AI key for analysis, for example `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, or `OPENAI_API_KEY`.

Recommended:

- `TUSHARE_TOKEN`
- `FINNHUB_API_KEY`
- `BRAVE_API_KEYS`

## 4. First login

Open the Render URL. Because `ADMIN_AUTH_ENABLED=true`, the first visit asks you to set the admin password.

Use a stronger password than `666666` if friends can access the URL.

## 5. Privacy notes

The URL is public, but the app requires a password. Anyone who knows the password can use the same account and data. For friends, prefer a future read-only/demo account.
```

- [ ] **Step 3: Verify YAML is parseable**

Run:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' - <<'PY'
import yaml
from pathlib import Path
data = yaml.safe_load(Path("render.yaml").read_text(encoding="utf-8"))
assert data["services"][0]["runtime"] == "docker"
assert any(env["key"] == "DATABASE_URL" and env.get("sync") is False for env in data["services"][0]["envVars"])
PY
```

Expected: exits with code 0.

---

### Task 4: Verify Build and Local Compatibility

**Files:**
- No new files.

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: confidence that local SQLite still works and cloud config is sane.

- [ ] **Step 1: Run focused Python tests**

Run:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_config_env_compat.py tests/test_storage.py -q
```

Expected: pass.

- [ ] **Step 2: Run frontend build check**

Run:

```powershell
$env:PATH='C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;' + $env:PATH
& 'D:\codex项目文件\gitup\github\apps\dsa-web\node_modules\.bin\tsc.cmd' -b
```

Expected: pass.

- [ ] **Step 3: Generate Render deeplink**

Use:

```text
https://dashboard.render.com/blueprint/new?repo=https://github.com/kaikai123421/codex
```

Before clicking the link, commit and push `github/render.yaml`, `src/config.py`, `requirements.txt`, and deployment docs to GitHub.

---

## Self-Review

- Spec coverage: Render free, external free database, password protection, secrets, and privacy notes are covered.
- Placeholder scan: no `TODO`, `TBD`, or vague validation steps remain.
- Type consistency: `Config.database_url` and `Config.get_db_url()` are used consistently.
