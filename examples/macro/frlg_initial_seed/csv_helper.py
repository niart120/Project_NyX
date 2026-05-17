"""CSV ヘルパー

初期Seed収集の CSV 読み書きを担当するユーティリティ。

2 ファイル構成:
- initial_seeds.csv       : 共有用（Seed 特定成功行のみ）
- initial_seeds_details.csv : 詳細ログ（全測定結果 + 逆算検証情報）

1測定=1行のフラット形式で追記する。
"""

from __future__ import annotations

import csv
from io import TextIOWrapper
from pathlib import Path

from nyxpy.framework.core.io.resources import OverwritePolicy, RunArtifactStore

from .config import FrlgInitialSeedConfig

# ================================================================
# CSV カラム定義
# ================================================================

# 共有用 (initial_seeds.csv)
CSV_FIELDNAMES: list[str] = [
    "frame",
    "seed",
    "region",
    "version",
    "edition",
    "sound_mode",
    "button_mode",
    "keyinput",
    "hardware",
    "fps",
    "note",
]

# 詳細ログ (initial_seeds_details.csv)
CSV_DETAIL_FIELDNAMES: list[str] = [
    "frame",
    "seed",
    "region",
    "version",
    "edition",
    "sound_mode",
    "button_mode",
    "keyinput",
    "hardware",
    "fps",
    "advance",
    "pokemon",
    "level",
    "hp",
    "atk",
    "def",
    "spa",
    "spd",
    "spe",
    "note",
]

CSV_FILENAME = "initial_seeds.csv"
CSV_DETAIL_FILENAME = "initial_seeds_details.csv"


def build_csv_path(cfg: FrlgInitialSeedConfig) -> Path:
    """共有用 CSV の run outputs 相対パスを返す。"""
    return _build_output_path(cfg, CSV_FILENAME)


def build_detail_csv_path(cfg: FrlgInitialSeedConfig) -> Path:
    """詳細ログ CSV の run outputs 相対パスを返す。"""
    return _build_output_path(cfg, CSV_DETAIL_FILENAME)


def build_debug_image_dir(cfg: FrlgInitialSeedConfig) -> Path:
    """デバッグ画像の run outputs 相対ディレクトリを返す。"""
    return _build_output_path(cfg, "img")


def _build_output_path(cfg: FrlgInitialSeedConfig, name: str) -> Path:
    output_dir = cfg.output_dir.strip()
    return Path(output_dir) / name if output_dir else Path(name)


def _append_row(csv_path: Path, fieldnames: list[str], row: dict[str, str]) -> None:
    """CSV の末尾に 1 行追加する。ファイルが存在しない場合はヘッダー付きで作成。"""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0

    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def append_csv_row(csv_path: Path, row: dict[str, str]) -> None:
    """共有用 CSV に 1 行追加する。"""
    _append_row(csv_path, CSV_FIELDNAMES, row)


def append_detail_csv_row(csv_path: Path, row: dict[str, str]) -> None:
    """詳細ログ CSV に 1 行追加する。"""
    _append_row(csv_path, CSV_DETAIL_FIELDNAMES, row)


def append_csv_artifact(
    artifacts: RunArtifactStore, output_path: Path, row: dict[str, str]
) -> None:
    """共有用 CSV を run outputs に追記する。"""
    _append_artifact_row(artifacts, output_path, CSV_FIELDNAMES, row)


def append_detail_csv_artifact(
    artifacts: RunArtifactStore, output_path: Path, row: dict[str, str]
) -> None:
    """詳細 CSV を run outputs に追記する。"""
    _append_artifact_row(artifacts, output_path, CSV_DETAIL_FIELDNAMES, row)


def _append_artifact_row(
    artifacts: RunArtifactStore,
    output_path: Path,
    fieldnames: list[str],
    row: dict[str, str],
) -> None:
    ref = artifacts.resolve_output_path(output_path)
    write_header = not ref.path.exists() or ref.path.stat().st_size == 0

    with artifacts.open_output(
        output_path,
        mode="ab",
        overwrite=OverwritePolicy.REPLACE,
        atomic=False,
    ) as raw:
        text = TextIOWrapper(raw, encoding="utf-8", newline="")
        try:
            writer = csv.DictWriter(text, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
            text.flush()
        finally:
            text.detach()
