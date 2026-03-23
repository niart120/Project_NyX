"""設定パラメータ定義

FRLG 野生乱数操作マクロの設定値を管理する dataclass。
仕様: spec/macro/frlg_wild_rng/spec.md §4
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FrlgWildRngConfig:
    """FRLG 野生乱数操作マクロの設定"""

    # === 基本設定 ===
    frame1: int = 2036
    target_advance: int = 2049
    fps: float = 60.0

    # === フレーム・RNG 補正 ===
    frame1_offset: float = 7.0
    platform_offset: int = -148
    user_offset: int = 0
    rng_multiplier: int = 2

    # === おしえテレビ設定 ===
    use_teachy_tv: bool = False
    teachy_tv_consumption: int = 0
    teachy_tv_adv_per_frame: int = 314
    teachy_tv_transition_correction: int = -12353

    @classmethod
    def from_args(cls, args: dict) -> FrlgWildRngConfig:
        """args dict から設定を構築する。"""
        cfg = cls()

        # 基本設定
        cfg.frame1 = int(args.get("frame1", cfg.frame1))
        cfg.target_advance = int(args.get("target_advance", cfg.target_advance))
        cfg.fps = float(args.get("fps", cfg.fps))

        # フレーム・RNG 補正
        cfg.frame1_offset = float(args.get("frame1_offset", cfg.frame1_offset))
        cfg.platform_offset = int(args.get("platform_offset", cfg.platform_offset))
        cfg.user_offset = int(args.get("user_offset", cfg.user_offset))
        cfg.rng_multiplier = int(args.get("rng_multiplier", cfg.rng_multiplier))

        # おしえテレビ設定
        cfg.use_teachy_tv = bool(args.get("use_teachy_tv", cfg.use_teachy_tv))
        cfg.teachy_tv_consumption = int(args.get("teachy_tv_consumption", cfg.teachy_tv_consumption))
        cfg.teachy_tv_adv_per_frame = int(
            args.get("teachy_tv_adv_per_frame", cfg.teachy_tv_adv_per_frame)
        )
        cfg.teachy_tv_transition_correction = int(
            args.get(
                "teachy_tv_transition_correction",
                cfg.teachy_tv_transition_correction,
            )
        )

        return cfg
