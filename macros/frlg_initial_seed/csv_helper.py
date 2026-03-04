"""CSV ヘルパー

初期Seed収集の CSV 読み書きを担当するユーティリティ。

2 ファイル構成:
- initial_seeds.csv       : 共有用（Seed 特定成功行のみ）
- initial_seeds_details.csv : 詳細ログ（全測定結果 + 逆算検証情報）

1測定=1行のフラット形式で追記する。
"""

from __future__ import annotations

import csv
from pathlib import Path

from .config import FrlgInitialSeedConfig

# ================================================================
# CSV カラム定義
# ================================================================

# 共有用 (initial_seeds.csv)
CSV_FIELDNAMES: list[str] = [
    "frame", "seed",
    "region", "version", "edition",
    "sound_mode", "button_mode", "keyinput",
    "hardware", "fps",
    "note",
]

# 詳細ログ (initial_seeds_details.csv)
CSV_DETAIL_FIELDNAMES: list[str] = [
    "frame", "seed",
    "region", "version", "edition",
    "sound_mode", "button_mode", "keyinput",
    "hardware", "fps",
    "advance", "pokemon", "level",
    "hp", "atk", "def", "spa", "spd", "spe",
    "note",
]

CSV_FILENAME = "initial_seeds.csv"
CSV_DETAIL_FILENAME = "initial_seeds_details.csv"


def build_csv_path(cfg: FrlgInitialSeedConfig) -> Path:
    """共有用 CSV パスを返す。"""
    return Path(cfg.output_dir) / CSV_FILENAME


def build_detail_csv_path(cfg: FrlgInitialSeedConfig) -> Path:
    """詳細ログ CSV パスを返す。"""
    return Path(cfg.output_dir) / CSV_DETAIL_FILENAME


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
