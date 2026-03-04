"""CSV ヘルパー

初期Seed収集の CSV 読み書きを担当するユーティリティ。
1測定=1行のフラット形式で追記する。
"""

from __future__ import annotations

import csv
from pathlib import Path

from .config import FrlgInitialSeedConfig

# CSV カラム定義
CSV_FIELDNAMES: list[str] = [
    "frame", "seed", "advance",
    "region", "version", "edition",
    "sound_mode", "button_mode", "keyinput",
]

CSV_FILENAME = "initial_seeds.csv"


def build_csv_path(cfg: FrlgInitialSeedConfig) -> Path:
    """固定ファイル名の CSV パスを返す。"""
    return Path(cfg.output_dir) / CSV_FILENAME


def append_csv_row(csv_path: Path, row: dict[str, str]) -> None:
    """CSV の末尾に 1 行追加する。ファイルが存在しない場合はヘッダー付きで作成。"""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0

    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
