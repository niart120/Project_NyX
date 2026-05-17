from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class RotationPolicy:
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 3
    retention_days: int = 14


def rotate_if_needed(path: Path, policy: RotationPolicy) -> None:
    path = Path(path)
    cleanup_retention(path, policy)
    if policy.max_bytes <= 0 or not path.exists() or path.stat().st_size < policy.max_bytes:
        return
    if policy.backup_count <= 0:
        path.unlink()
        return

    oldest = _rotated_path(path, policy.backup_count)
    if oldest.exists():
        oldest.unlink()
    for index in range(policy.backup_count - 1, 0, -1):
        source = _rotated_path(path, index)
        if source.exists():
            source.replace(_rotated_path(path, index + 1))
    path.replace(_rotated_path(path, 1))


def cleanup_retention(path: Path, policy: RotationPolicy) -> None:
    if policy.retention_days <= 0:
        return
    cutoff = datetime.now() - timedelta(days=policy.retention_days)
    for candidate in Path(path).parent.glob(Path(path).name + ".*"):
        if datetime.fromtimestamp(candidate.stat().st_mtime) < cutoff:
            candidate.unlink()


def cleanup_retention_glob(base_dir: Path, pattern: str, retention_days: int) -> None:
    if retention_days <= 0:
        return
    cutoff = datetime.now() - timedelta(days=retention_days)
    for candidate in Path(base_dir).glob(pattern):
        if candidate.is_file() and datetime.fromtimestamp(candidate.stat().st_mtime) < cutoff:
            candidate.unlink()


def _rotated_path(path: Path, index: int) -> Path:
    return path.with_name(f"{path.name}.{index}")
