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
    target_advance: int = 610
    target_item: str = "ゴージャスボール"
    target_count: int = 9999
    target_pokemon: list[str] = field(default_factory=list)
    pokedex: list[int] = field(default_factory=list)
    fps: float = 60.0

    # === フレーム・RNG 補正 ===
    frame1_offset: int = 0
    advance_offset: int = 322
    rng_multiplier: int = 2

    # === デバッグ ===
    screenshot_mode: bool = False

    @classmethod
    def from_args(cls, args: dict) -> FrlgGorgeousResortConfig:
        """args dict から設定を構築する。"""
        cfg = cls()

        # 基本設定
        cfg.language = str(args.get("language", cfg.language))
        cfg.frame1 = int(args.get("frame1", cfg.frame1))
        cfg.target_advance = int(args.get("target_advance", cfg.target_advance))
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

        # フレーム・RNG 補正
        cfg.frame1_offset = int(args.get("frame1_offset", cfg.frame1_offset))
        cfg.advance_offset = int(args.get("advance_offset", cfg.advance_offset))
        cfg.rng_multiplier = int(args.get("rng_multiplier", cfg.rng_multiplier))

        # デバッグ
        cfg.screenshot_mode = bool(args.get("screenshot_mode", cfg.screenshot_mode))

        return cfg
