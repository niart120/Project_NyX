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


def load_frame_counts(
    csv_path: Path, cfg: FrlgInitialSeedConfig
) -> dict[int, int]:
    """既存 CSV を読み込み、現在の設定に一致する行のフレームごとの測定回数を返す。

    Returns:
        {frame: count} — 現在の設定 (region/version/edition/sound_mode/button_mode/keyinput)
        に一致する行のみをカウント。
    """
    counts: dict[int, int] = {}
    if not csv_path.exists():
        return counts

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (
                row.get("region") == cfg.language
                and row.get("version") == cfg.rom
                and row.get("edition") == cfg.device
                and row.get("sound_mode") == cfg.sound_mode
                and row.get("button_mode") == cfg.button_mode
                and row.get("keyinput") == cfg.keyinput
            ):
                frame = int(row["frame"])
                counts[frame] = counts.get(frame, 0) + 1

    return counts


def append_csv_row(csv_path: Path, row: dict[str, str]) -> None:
    """CSV の末尾に 1 行追加する。ファイルが存在しない場合はヘッダー付きで作成。"""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0

    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
