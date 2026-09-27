# CI/CD & Automated Quality Gates Specification (Phase 18)

This document details the continuous integration (CI) architecture, automated quality gates, security policies, and local reproducibility guidelines for the **Real-Time AI Gym Trainer** platform.

---

## 1. CI/CD Architecture Overview

The automated quality pipeline runs on GitHub Actions on every `push` and `pull_request` targeting `main` and feature branches.

```
                              ┌────────────────────────────────────────┐
                              │            GitHub Event                │
                              │        (push / pull_request)           │
                              └──────────────────┬─────────────────────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   ▼                             ▼                             ▼
        ┌─────────────────────┐       ┌─────────────────────┐       ┌─────────────────────┐
        │  Job 1: Security    │       │  Job 2: Backend     │       │  Job 3: Migrations  │
        │ - Secret Hygiene    │       │ - Ruff Linter       │       │ - PostgreSQL 15 Svc │
        │ - Private Key Scan  │       │ - Pytest (293 tests)│       │ - Upgrade to head   │
        │ - Dependency Audit  │       │ - Coverage (>= 80%) │       │ - Downgrade (-1)    │
        │                     │       │ - XML Artifact Upload│      │ - Re-upgrade head   │
        └─────────────────────┘       └──────────┬──────────┘       └─────────────────────┘
                                                 │
                                                 ▼
                                      ┌─────────────────────┐
                                      │  Job 4: Frontend    │
                                      │ - npm ci (lockfile) │
                                      │ - npm test (33 test)│
                                      │ - tsc --noEmit      │
                                      │ - ESLint            │
                                      │ - Standalone Build  │
                                      └──────────┬──────────┘
                                                 │
                                                 ▼
                                      ┌─────────────────────┐
                                      │  Job 5: Docker      │
                                      │ - Compose Config    │
                                      │ - Backend Image     │
                                      │ - Frontend Image    │
                                      │ - Health Check Probe│
                                      └─────────────────────┘
```

---

## 2. Matrix & Supported Runtime Environments

| Component | Target Version | CI Environment | Docker Base Image |
| :--- | :--- | :--- | :--- |
| **OS Runner** | Ubuntu 22.04 LTS | `ubuntu-latest` | Linux x86_64 |
| **Python Backend** | `3.11` | Python 3.11 (`actions/setup-python@v5`) | `python:3.11-slim-bookworm` |
| **Node.js Frontend** | `20.x` (LTS) | Node.js 20 (`actions/setup-node@v4`) | `node:20-alpine` |
| **Database** | PostgreSQL `15` | `postgres:15-alpine` service container | `postgres:15-alpine` |
| **Docker Compose** | Compose v2 | Built-in GitHub Actions Docker Engine | Docker Compose |

---

## 3. Workflow Jobs & Quality Gates

### Job 1: Security & Secret Hygiene (`security`)
- **Untracked Environment Verification**: Enforces that `.env`, `.env.local`, and other environment configuration files containing production secrets are strictly excluded from the Git index (`git ls-files --error-unmatch .env`).
- **Private Key / Certificate Detection**: Scans repository sources for unencrypted PEM/RSA private key patterns (`BEGIN PRIVATE KEY`).
- **Supply-Chain Dependency Audit**: Validates production dependencies using `npm audit --omit=dev --audit-level=critical`.

### Job 2: Backend Quality & Coverage (`backend`)
- **System Dependencies**: Installs `libgl1` and `libglib2.0-0` required for OpenCV headless image processing and MediaPipe landmark extraction.
- **Dependency Caching**: Utilizes GitHub Actions pip caching against `backend/requirements-dev.txt`.
- **Linting & Code Style**: Runs `ruff check .` with zero allowed warnings/errors.
- **Test Suite & Strict Coverage Gate**:
  - Executes full test suite (293 unit, integration, and E2E tests).
  - Enforces minimum code coverage threshold of **80%** (measured project baseline: **87.25%** across backend and ai modules).
  - Command: `pytest --cov=backend/app --cov=ai --cov-report=term-missing --cov-report=xml:reports/coverage.xml --cov-fail-under=80`.
  - Emits XML coverage artifact retained for 14 days.

### Job 3: Database Migrations (`migrations`)
- **Isolated PostgreSQL Service**: Spins up a clean `postgres:15-alpine` container with native health checks (`pg_isready`).
- **Alembic Reversibility & Integrity Gate**:
  1. `alembic upgrade head` — Validates forward schema creation.
  2. Asserts current revision matches head (`004_add_performance_indexes`).
  3. `alembic downgrade -1` — Validates schema rollback capability.
  4. Asserts downgraded revision (`003_add_user_profile_table`).
  5. `alembic upgrade head` — Validates re-upgrade back to head.
  6. Asserts final state is clean and at head.

### Job 4: Frontend Quality & Build (`frontend`)
- **Deterministic Dependency Installation**: Runs `npm ci` strictly from `frontend/package-lock.json`.
- **Unit & Integration Tests**: Executes all 33 Next.js tests via `npm test` (`tsx --test`).
- **TypeScript Static Verification**: Runs `tsc --noEmit` to prevent type regressions.
- **Code Linter**: Runs `npm run lint` (`next lint`).
- **Production Build**: Executes `npm run build` validating that the standalone server bundle compiles without bundling errors.

### Job 5: Docker & Container Integrity (`docker`)
- **Compose Validation**: Verifies `docker-compose.yml` syntax using `docker compose config --quiet`.
- **Production Image Builds**: Builds `ai-gym-trainer-backend` and `ai-gym-trainer-frontend`.
- **Container Health Probes**:
  - Launches containers in detached mode (`docker compose up -d`).
  - Polls health status until `ai_gym_backend` and `ai_gym_frontend` report `healthy`.
  - Verifies HTTP 200 on backend (`http://localhost:8000/health`) and frontend (`http://localhost:3000/`).
  - Cleans up containers and networks (`docker compose down -v`).

---

## 4. What CI Intentionally Does NOT Run

To keep CI execution fast, cost-efficient, and deterministic:
1. **Multi-Gigabyte Ollama Model Downloads**: CI does **not** download multi-gigabyte LLM models (e.g. `llama3.2` ~2.0 GB). The application's verified deterministic fallback handles AI Coach requests safely in CI environments.
2. **GPU Passthrough**: CI runs in standard CPU container environments.
3. **External Cloud Deployments**: CI verifies merge-readiness only and does not deploy to production.

---

## 5. Local Reproducibility

Developers can reproduce all primary CI checks locally before submitting pull requests.

### Python Cross-Platform Runner:
```bash
python scripts/run_ci_checks.py
```

### Windows PowerShell Runner:
```powershell
.\scripts\run_ci_checks.ps1
```

### Manual Individual Commands:
```bash
# 1. Backend Linting & Tests
ruff check .
pytest --cov=backend/app --cov=ai --cov-report=term --cov-fail-under=80

# 2. Frontend Tests & Build
cd frontend
npm test
npm run typecheck
npm run lint
npm run build

# 3. Docker Compose Verification
docker compose config --quiet
docker compose build
```
