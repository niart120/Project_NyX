"""設定パラメータ定義

FRLG ゴージャスリゾート アキホおねだりマクロの設定値を管理する dataclass。
仕様: spec/macro/frlg_gorgeous_resort/spec.md §2
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FrlgGorgeousResortConfig:
    """FRLG ゴージャスリゾート アキホおねだりマクロの設定"""

    # === 基本設定 ===
    language: str = "JPN"
    frame1: int = 2347
    frame2: int = 610
    target_item: str = "ゴージャスボール"
    target_count: int = 9999
    target_pokemon: list[str] = field(default_factory=list)
    pokedex: list[int] = field(default_factory=list)
    fps: float = 60.0

    # === フレーム補正 ===
    frame1_offset: int = 0
    frame2_offset: int = 322

    # === デバッグ ===
    screenshot_mode: bool = False

    @classmethod
    def from_args(cls, args: dict) -> FrlgGorgeousResortConfig:
        """args dict から設定を構築する。"""
        cfg = cls()

        # 基本設定
        cfg.language = str(args.get("language", cfg.language))
        cfg.frame1 = int(args.get("frame1", cfg.frame1))
        cfg.frame2 = int(args.get("frame2", cfg.frame2))
        cfg.target_item = str(args.get("target_item", cfg.target_item))
        cfg.target_count = int(args.get("target_count", cfg.target_count))
        cfg.fps = float(args.get("fps", cfg.fps))

        # target_pokemon: list[str]
        tp = args.get("target_pokemon")
        if tp is not None:
            cfg.target_pokemon = [str(v) for v in tp]

        # pokedex: list[int]
        pd = args.get("pokedex")
        if pd is not None:
            cfg.pokedex = [int(v) for v in pd]

        # フレーム補正
        cfg.frame1_offset = int(args.get("frame1_offset", cfg.frame1_offset))
        cfg.frame2_offset = int(args.get("frame2_offset", cfg.frame2_offset))

        # デバッグ
        cfg.screenshot_mode = bool(args.get("screenshot_mode", cfg.screenshot_mode))

        return cfg
