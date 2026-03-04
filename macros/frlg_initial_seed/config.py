"""設定パラメータ定義

FRLG 初期Seed特定マクロの設定値を管理する dataclass。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class KeyInput(StrEnum):
    """ゲーム起動時のキー入力パターン。

    通常モードでは NONE を使用。Phase 2 のキー入力調査モードで他の値を使用する。
    """

    NONE = "none"
    DPAD_ON_BOOT = "dpad_on_boot"
    A_ON_BOOT = "a_on_boot"
    DPAD_AFTER_FADE = "dpad_after_fade"
    A_AFTER_FADE = "a_after_fade"


@dataclass
class FrlgInitialSeedConfig:
    """FRLG 初期Seed特定マクロの設定"""

    # === 基本設定 ===
    language: str = "JPN"
    rom: str = "FR"
    device: str = "Switch"
    output_dir: str = "static/frlg_initial_seed"
    sound_mode: str = "モノラル"
    button_mode: str = "ヘルプ"
    keyinput: KeyInput = KeyInput.NONE

    # === フレームタイミング ===
    min_frame: int = 2000
    max_frame: int = 2180
    trials: int = 3
    frame2: int = 560
    frame1_offset: int = 0
    frame2_offset: int = 0
    min_advance: int = 1330
    max_advance: int = 1350
    fps: float = 60.0

    # === 対象ポケモン ===
    base_stats: tuple[int, int, int, int, int, int] = (106, 90, 130, 90, 154, 110)
    level: int = 70

    @classmethod
    def from_args(cls, args: dict) -> "FrlgInitialSeedConfig":
        """args dict から設定を構築する。"""
        cfg = cls()
        cfg.language = str(args.get("language", cfg.language))
        cfg.rom = str(args.get("rom", cfg.rom))
        cfg.device = str(args.get("device", cfg.device))
        cfg.output_dir = str(args.get("output_dir", cfg.output_dir))
        cfg.sound_mode = str(args.get("sound_mode", cfg.sound_mode))
        cfg.button_mode = str(args.get("button_mode", cfg.button_mode))
        cfg.keyinput = KeyInput(args.get("keyinput", cfg.keyinput))

        cfg.min_frame = int(args.get("min_frame", cfg.min_frame))
        cfg.max_frame = int(args.get("max_frame", cfg.max_frame))
        cfg.trials = int(args.get("trials", cfg.trials))
        cfg.frame2 = int(args.get("frame2", cfg.frame2))
        cfg.frame1_offset = int(args.get("frame1_offset", cfg.frame1_offset))
        cfg.frame2_offset = int(args.get("frame2_offset", cfg.frame2_offset))
        cfg.min_advance = int(args.get("min_advance", cfg.min_advance))
        cfg.max_advance = int(args.get("max_advance", cfg.max_advance))
        cfg.fps = float(args.get("fps", cfg.fps))

        cfg.level = int(args.get("level", cfg.level))

        base = args.get("base_stats")
        if base is not None:
            cfg.base_stats = tuple(int(v) for v in base)

        return cfg
