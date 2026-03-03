"""設定パラメータ定義

FRLG 初期Seed特定マクロの設定値を管理する dataclass。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FrlgInitialSeedConfig:
    """FRLG 初期Seed特定マクロの設定"""

    # === 基本設定 ===
    language: str = "JPN"
    rom: str = "FR"
    device: str = "Switch"
    output_dir: str = "static/frlg_initial_seed"
    sound: str = "モノラル"
    button_mode: str = "ヘルプ"

    # === フレームタイミング ===
    min_frame: int = 2000
    max_frame: int = 2180
    trials: int = 3
    frame2: int = 560
    frame1_offset: int = 0
    frame2_offset: int = 0
    min_advance: int = 1300
    max_advance: int = 1400
    fps: float = 60.0

    # === 対象ポケモン ===
    base_stats: tuple[int, int, int, int, int, int] = (106, 90, 130, 90, 154, 110)
    level: int = 70

    @property
    def file_name(self) -> str:
        """設定値からファイル名を自動生成する。

        フォーマット: {language}_{rom}_{device}_{sound}_{button_mode}_{min_frame}_{max_frame}
        """
        return (
            f"{self.language}_{self.rom}_{self.device}"
            f"_{self.sound}_{self.button_mode}"
            f"_{self.min_frame}_{self.max_frame}"
        )

    @classmethod
    def from_args(cls, args: dict) -> "FrlgInitialSeedConfig":
        """args dict から設定を構築する。"""
        cfg = cls()
        cfg.language = str(args.get("language", cfg.language))
        cfg.rom = str(args.get("rom", cfg.rom))
        cfg.device = str(args.get("device", cfg.device))
        cfg.output_dir = str(args.get("output_dir", cfg.output_dir))
        cfg.sound = str(args.get("sound", cfg.sound))
        cfg.button_mode = str(args.get("button_mode", cfg.button_mode))

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
