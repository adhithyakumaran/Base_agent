"""P10.2 — atomic filesystem writes and cooperative file locks."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

T = TypeVar("T")


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)


def atomic_write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    atomic_write_text(path, json.dumps(payload, indent=indent), encoding="utf-8")


@contextmanager
def file_lock(lock_path: Path, *, timeout_s: float = 30.0, poll_s: float = 0.02) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout_s
    acquired = False
    while time.time() < deadline:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
            os.close(fd)
            acquired = True
            break
        except FileExistsError:
            time.sleep(poll_s)
    if not acquired:
        raise TimeoutError(f"timed out acquiring lock: {lock_path}")
    try:
        yield
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def run_lock_path(base_dir: Path, run_id: str) -> Path:
    return Path(base_dir) / ".locks" / f"{run_id}.lock"


def resource_lock_path(base_dir: Path, resource: str) -> Path:
    safe = resource.replace("/", "_").replace("\\", "_")
    return Path(base_dir) / ".locks" / f"{safe}.lock"


@contextmanager
def run_file_lock(base_dir: Path | str, run_id: str, *, timeout_s: float = 30.0) -> Iterator[None]:
    with file_lock(run_lock_path(Path(base_dir), run_id), timeout_s=timeout_s):
        yield


@contextmanager
def named_lock(base_dir: Path | str, name: str, *, timeout_s: float = 30.0) -> Iterator[None]:
    with file_lock(resource_lock_path(Path(base_dir), name), timeout_s=timeout_s):
        yield


def mutate_json_file(
    path: Path,
    *,
    lock_path: Path,
    default: Callable[[], Any],
    mutator: Callable[[Any], Any],
    timeout_s: float = 30.0,
) -> Any:
    with file_lock(lock_path, timeout_s=timeout_s):
        if path.exists():
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                current = default()
        else:
            current = default()
        updated = mutator(current)
        atomic_write_json(path, updated)
        return updated
