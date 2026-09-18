"""Shared fixtures for generation pipeline tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


def _copy_automation_tree(root: Path) -> None:
    real = Path("apps/automation").resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "tests" / "product").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "product" / "QA-PARAM-SKU.spec.ts").write_text("// existing param test", encoding="utf-8")
    (root / "generated" / "drafts").mkdir(parents=True, exist_ok=True)
    (root / "generated" / "journals").mkdir(parents=True, exist_ok=True)

    for name in (
        "playwright.config.ts",
        "playwright.drafts.config.ts",
        "tsconfig.json",
        "tsconfig.generated.json",
        "global-setup.ts",
    ):
        src = real / name
        if src.exists():
            shutil.copy2(src, root / name)

    if (real / "src").exists():
        shutil.copytree(real / "src", root / "src", dirs_exist_ok=True)
    if (real / "scripts").exists():
        shutil.copytree(real / "scripts", root / "scripts", dirs_exist_ok=True)
    if (real / "node_modules").exists() and not (root / "node_modules").exists():
        (root / "node_modules").symlink_to(real / "node_modules")
    if (real / "package.json").exists():
        shutil.copy2(real / "package.json", root / "package.json")


@pytest.fixture
def automation_dir(tmp_path: Path) -> Path:
    root = tmp_path / "automation"
    _copy_automation_tree(root)
    return root
