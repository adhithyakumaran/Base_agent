#!/usr/bin/env python3
"""Verify local setup before running QA agent. Run from repo root."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTOMATION = ROOT / "automation"
ENV_FILE = ROOT / ".env"
AUTOMATION_ENV = AUTOMATION / "config" / ".env"


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "OK" if ok else "FAIL"
    line = f"[{mark}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok


def main() -> int:
    print(f"Repo root: {ROOT}\n")
    all_ok = True

    py = sys.executable
    all_ok &= check("Python", True, py)

    try:
        import litellm  # noqa: F401

        all_ok &= check("litellm (Groq LLM)", True)
    except ImportError:
        all_ok &= check("litellm (Groq LLM)", False, 'run: pip install -e ".[llm]"')

    groq = os.environ.get("GROQ_API_KEY") or _read_env_key("GROQ_API_KEY")
    all_ok &= check("GROQ_API_KEY in .env", bool(groq), ENV_FILE.as_posix())

    node = shutil.which("node") or _which_win("node")
    npm = shutil.which("npm") or _which_win("npm")
    all_ok &= check("node on PATH", bool(node), node or "install Node.js LTS")
    all_ok &= check("npm on PATH", bool(npm), npm or "install Node.js LTS")

    all_ok &= check("automation/", AUTOMATION.is_dir(), AUTOMATION.as_posix())
    nm = AUTOMATION / "node_modules"
    all_ok &= check("automation/node_modules", nm.is_dir(), "run: cd automation && npm ci")

    if npm and nm.is_dir():
        try:
            proc = subprocess.run(
                _npm_cmd("run test:sanity -- --list"),
                cwd=str(AUTOMATION),
                capture_output=True,
                text=True,
                timeout=120,
                shell=_use_shell(),
                env=_enriched_env(),
            )
            listed = proc.returncode == 0 or "BF-" in (proc.stdout + proc.stderr)
            all_ok &= check(
                "npm run test:sanity (dry list)",
                listed,
                proc.stderr.strip()[:200] or f"exit {proc.returncode}",
            )
        except Exception as exc:
            all_ok &= check("npm run test:sanity (dry list)", False, str(exc))

    all_ok &= check(
        "UAT credentials",
        AUTOMATION_ENV.is_file(),
        f"create {AUTOMATION_ENV.as_posix()} from environments.example.env",
    )

    print()
    if all_ok:
        print("All checks passed. Start agent server from repo root:")
        print("  python scripts/local_agent_server.py --port 43124")
    else:
        print("Fix FAIL items above, then restart the agent server.")
    return 0 if all_ok else 1


def _read_env_key(key: str) -> str:
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _which_win(name: str) -> str | None:
    if sys.platform != "win32":
        return None
    for base in _node_dirs():
        for suffix in ("", ".cmd", ".exe"):
            p = base / f"{name}{suffix}"
            if p.exists():
                return str(p)
    return None


def _node_dirs() -> list[Path]:
    dirs: list[Path] = []
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pfx = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    appdata = os.environ.get("APPDATA", "")
    for raw in (f"{pf}\\nodejs", f"{pfx}\\nodejs", f"{appdata}\\npm"):
        p = Path(raw)
        if p.is_dir():
            dirs.append(p)
    return dirs


def _enriched_env() -> dict[str, str]:
    env = os.environ.copy()
    if sys.platform == "win32":
        extra = os.pathsep.join(str(d) for d in _node_dirs())
        env["PATH"] = extra + os.pathsep + env.get("PATH", "")
    return env


def _use_shell() -> bool:
    return sys.platform == "win32"


def _npm_cmd(args: str) -> str | list[str]:
    npm = shutil.which("npm", path=_enriched_env().get("PATH")) or _which_win("npm")
    if not npm:
        return "npm " + args
    if sys.platform == "win32":
        return subprocess.list2cmdline([npm, *args.split()])
    return [npm, *args.split()]


if __name__ == "__main__":
    raise SystemExit(main())
