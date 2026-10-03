#!/usr/bin/env python3
"""
Cross-Platform Local CI Quality Gate Runner for Real-Time AI Gym Trainer.

Reproduces all core checks executed in the GitHub Actions CI pipeline:
1. Secret and sensitive file scanning
2. Backend code linting (Ruff)
3. Backend test suite & coverage gate (Pytest + Coverage)
4. Frontend unit/integration tests
5. Frontend TypeScript typecheck
6. Frontend ESLint
7. Frontend Next.js production build

Exit code 0 on all gates passing; non-zero if any gate fails.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_command(cmd: list[str], cwd: Path | None = None) -> bool:
    cwd_path = cwd or ROOT_DIR
    print(f"Running: {' '.join(cmd)} (in {cwd_path.name})")
    res = subprocess.run(cmd, cwd=cwd_path)
    if res.returncode != 0:
        print(f"FAILED (exit code {res.returncode})")
        return False
    print("PASSED")
    return True


def check_secrets() -> bool:
    print_header("Gate 1: Secret & Sensitive File Scan")
    # 1. Check for tracked .env files
    tracked_res = subprocess.run(
        ["git", "ls-files", ".env", ".env.local"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    if tracked_res.stdout.strip():
        print(f"FAILED: Sensitive environment files are tracked: {tracked_res.stdout.strip()}")
        return False
    print("No sensitive .env files tracked in Git index.")

    # 2. Check for private keys in code
    target_pattern = "-----" + "BEGIN"
    key_patterns = [target_pattern + " RSA PRIVATE KEY", target_pattern + " PRIVATE KEY"]
    for ext in [".py", ".ts", ".tsx", ".json", ".yml", ".yaml"]:
        for file in ROOT_DIR.rglob(f"*{ext}"):
            if any(p in file.parts for p in [".git", "node_modules", ".venv", ".next"]):
                continue
            if file.name == "run_ci_checks.py":
                continue
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                if any(pat in content for pat in key_patterns):
                    print(f"FAILED: Private key detected in {file}")
                    return False
            except Exception:
                pass
    print("No unencrypted private keys detected.")
    return True


def check_backend() -> bool:
    print_header("Gate 2: Backend Quality & Coverage")

    python_executable = sys.executable
    # Check if .venv python is available
    venv_py = ROOT_DIR / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    if venv_py.exists():
        python_executable = str(venv_py)

    # 1. Ruff linting
    if not run_command([python_executable, "-m", "ruff", "check", "."]):
        return False

    # 2. Pytest + coverage (fail under 80%)
    pytest_cmd = [
        python_executable,
        "-m",
        "pytest",
        "--cov=backend/app",
        "--cov=ai",
        "--cov-report=term",
        "--cov-fail-under=80",
    ]
    if not run_command(pytest_cmd):
        return False

    return True


def check_frontend() -> bool:
    print_header("Gate 3: Frontend Quality & Build")
    frontend_dir = ROOT_DIR / "frontend"
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

    # 1. Frontend tests
    if not run_command([npm_cmd, "test"], cwd=frontend_dir):
        return False

    # 2. Typecheck
    if not run_command([npm_cmd, "run", "typecheck"], cwd=frontend_dir):
        return False

    # 3. ESLint
    if not run_command([npm_cmd, "run", "lint"], cwd=frontend_dir):
        return False

    # 4. Production build
    if not run_command([npm_cmd, "run", "build"], cwd=frontend_dir):
        return False

    return True


def main():
    print("=" * 70)
    print("  Real-Time AI Gym Trainer — Local CI Quality Gate Pipeline")
    print("=" * 70)

    stages = [
        ("Secret Scan", check_secrets),
        ("Backend Quality & Coverage", check_backend),
        ("Frontend Quality & Build", check_frontend),
    ]

    failed_stages = []
    for name, stage_fn in stages:
        try:
            if not stage_fn():
                failed_stages.append(name)
        except Exception as e:
            print(f"Exception during {name}: {e}")
            failed_stages.append(name)

    print("\n" + "=" * 70)
    print("  CI PIPELINE SUMMARY")
    print("=" * 70)
    if failed_stages:
        print(f"FAILED GATES: {', '.join(failed_stages)}")
        sys.exit(1)
    else:
        print("ALL CI QUALITY GATES PASSED CLEANLY!")
        sys.exit(0)


if __name__ == "__main__":
    main()
