"""
リージョン別タイミング定義

各リージョンの会話送りタイミング・フレーム補正値などを
データ駆動で管理するモジュール。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegionTiming:
    """リージョンごとのタイミング定義"""

    frame3_offset: float
    """Frame3 に適用するリージョン固有の補正値（減算）"""

    intro_pre_wait: float
    """Step 4 冒頭の追加 wait (秒)。JPN=0, ENG=0.5, etc."""

    intro_sequence: list[tuple[float, float]]
    """イントロ会話送りの (dur, wait) シーケンス"""

    name_confirm_sequence: list[tuple[float, float]]
    """名前決定後〜ライバル登場 (Step 9) の (dur, wait) シーケンス"""

    rival_confirm_sequence: list[tuple[float, float]]
    """ライバル名確定後の会話 (Step 11) の (dur, wait) シーケンス"""

    game_start_wait: float
    """ゲーム開始 (Step 13) の待機秒数。JPN=5.0, 他=6.5"""

    report_a_presses: int
    """レポート書き込み時の A 押下回数"""

    report_a_wait: float
    """レポート書き込み時の各 A 後の待機秒数"""

    tid_roi: tuple[int, int, int, int]
    """TID OCR 用 ROI (x, y, w, h) — 720p 基準"""

    intro_sequence_no_save: list[tuple[float, float]] | None = field(default=None)
    """セーブデータなし時のイントロ会話送りシーケンス。
    None の場合は intro_sequence を使用する。"""

    name_confirm_sequence_no_save: list[tuple[float, float]] | None = field(default=None)
    """セーブデータなし時の名前決定後〜ライバル登場シーケンス。
    None の場合は name_confirm_sequence を使用する。"""

    rival_confirm_sequence_no_save: list[tuple[float, float]] | None = field(default=None)
    """セーブデータなし時のライバル名確定後の会話シーケンス。
    None の場合は rival_confirm_sequence を使用する。"""


# ============================================================
# リージョン別タイミングテーブル
# ============================================================

REGION_TIMINGS: dict[str, RegionTiming] = {
    # ----------------------------------------------------------
    # JPN
    # ----------------------------------------------------------
    "JPN": RegionTiming(
        frame3_offset=143,
        intro_pre_wait=0.0,
        intro_sequence=[
            # オーキド博士
            (0.1, 0.6),
            (0.1, 0.6),
            (0.1, 0.4),
            # ニドラン♀登場
            (0.1, 1.6),
            (0.1, 0.5),
            (0.1, 0.6),
            (0.1, 0.5),
            (0.1, 0.5),
            (0.1, 0.7),
            # ニドラン♀退場
            (0.1, 2.6),
            (0.1, 2.3),
        ],
        name_confirm_sequence=[
            # 名前決定
            (0.1, 1.8),
            (0.1, 2.5),
            # ライバル登場
            (0.1, 0.7),
            (0.1, 0.7),
            (0.1, 0.7),
        ],
        rival_confirm_sequence=[
            # 名前確定
            (0.1, 0.7),
            (0.1, 2.4),
            # 会話
            (0.1, 0.7),
            (0.1, 0.7),
        ],
        game_start_wait=5.0,
        report_a_presses=7,
        report_a_wait=1.0,
        tid_roi=(860, 80, 220, 65),
        # セーブデータなし時 (「はなしのはやさ」がデフォルト速度) 用シーケンス
        # wait 値はセーブデータありの約 4 倍を基準に設定
        intro_sequence_no_save=[
            # オーキド博士
            (0.1, 2.0),
            (0.1, 2.4),
            (0.1, 1.6),
            # ニドラン♀登場
            (0.1, 3.6),
            (0.1, 2.0),
            (0.1, 2.4),
            (0.1, 1.8),
            (0.1, 1.0),
            (0.1, 2.8),
            # ニドラン♀退場
            (0.1, 4.1),
            (0.1, 3.8),
        ],
        name_confirm_sequence_no_save=[
            # 名前決定
            (0.1, 2.5),
            (0.1, 2.0),
            # ライバル登場
            (0.1, 2.0),
            (0.1, 2.0),
            (0.1, 2.8),
        ],
        rival_confirm_sequence_no_save=[
            # 名前確定
            (0.1, 2.0),
            (0.1, 3.0),
            # 会話
            (0.1, 2.8),
            (0.1, 2.8),
        ],
    ),
    # ----------------------------------------------------------
    # ENG
    # ----------------------------------------------------------
    "ENG": RegionTiming(
        frame3_offset=198,
        intro_pre_wait=0.5,
        intro_sequence=[
            # オーキド博士
            (0.1, 1.0),
            (0.1, 0.6),
            (0.1, 1.1),
            # ニドラン♀登場
            (0.1, 2.1),
            (0.1, 1.3),
            (0.1, 0.6),
            (0.1, 0.6),
            # ニドラン♀退場
            (0.1, 2.9),
            (0.1, 2.6),
        ],
        name_confirm_sequence=[
            # 名前決定
            (0.1, 2.2),
            (0.1, 2.8),
            # ライバル登場
            (0.1, 1.3),
            (0.1, 1.1),
        ],
        rival_confirm_sequence=[
            # 名前確定
            (0.1, 0.9),
            (0.1, 2.4),
            # 会話
            (0.1, 0.9),
        ],
        game_start_wait=6.5,
        report_a_presses=6,
        report_a_wait=1.5,
        tid_roi=(888, 86, 127, 47),
    ),
    # ----------------------------------------------------------
    # FRA
    # ----------------------------------------------------------
    "FRA": RegionTiming(
        frame3_offset=154,
        intro_pre_wait=1.0,
        intro_sequence=[
            # オーキド博士
            (0.1, 0.6),
            (0.1, 1.2),
            # ニドラン♀登場
            (0.1, 1.9),
            (0.1, 1.4),
            (0.1, 0.7),
            (0.1, 0.6),
            (0.1, 1.0),
            # ニドラン♀退場
            (0.1, 2.7),
            (0.1, 2.6),
        ],
        name_confirm_sequence=[
            # 名前決定
            (0.1, 2.5),
            (0.1, 2.8),
            # ライバル登場
            (0.1, 1.2),
            (0.1, 1.6),
        ],
        rival_confirm_sequence=[
            # 名前確定
            (0.1, 1.2),
            (0.1, 2.9),
            # 会話
            (0.1, 1.0),
            (0.1, 1.5),
        ],
        game_start_wait=6.5,
        report_a_presses=6,
        report_a_wait=1.5,
        tid_roi=(893, 86, 127, 47),
    ),
    # ----------------------------------------------------------
    # ITA
    # ----------------------------------------------------------
    "ITA": RegionTiming(
        frame3_offset=185,
        intro_pre_wait=1.0,
        intro_sequence=[
            # オーキド博士 — FRA と同一
            (0.1, 0.6),
            (0.1, 1.2),
            # ニドラン♀登場
            (0.1, 1.9),
            (0.1, 1.4),
            (0.1, 0.7),
            (0.1, 0.6),
            (0.1, 1.0),
            # ニドラン♀退場
            (0.1, 2.7),
            (0.1, 2.6),
        ],
        name_confirm_sequence=[
            # 名前決定
            (0.1, 2.5),
            (0.1, 2.8),
            # ライバル登場
            (0.1, 1.6),
        ],
        rival_confirm_sequence=[
            # 名前確定
            (0.1, 1.2),
            (0.1, 2.9),
            # 会話
            (0.1, 1.0),
            (0.1, 1.5),
        ],
        game_start_wait=6.5,
        report_a_presses=7,
        report_a_wait=1.5,
        tid_roi=(893, 86, 127, 47),
    ),
    # ----------------------------------------------------------
    # ESP
    # ----------------------------------------------------------
    "ESP": RegionTiming(
        frame3_offset=151,
        intro_pre_wait=0.5,
        intro_sequence=[
            # オーキド博士
            (0.1, 0.6),
            (0.1, 1.2),
            # ニドラン♀登場
            (0.1, 1.6),
            (0.1, 0.9),
            (0.1, 0.4),
            (0.1, 0.4),
            (0.1, 0.7),
            (0.1, 0.7),
            # ニドラン♀退場
            (0.1, 2.6),
            (0.1, 2.4),
        ],
        name_confirm_sequence=[
            # 名前決定
            (0.1, 2.2),
            (0.1, 2.5),
            # ライバル登場
            (0.1, 1.1),
            (0.1, 1.6),
        ],
        rival_confirm_sequence=[
            # 名前確定
            (0.1, 0.7),
            (0.1, 2.4),
            # 会話
            (0.1, 0.9),
            (0.1, 0.9),
        ],
        game_start_wait=6.5,
        report_a_presses=6,
        report_a_wait=1.5,
        tid_roi=(915, 86, 127, 47),
    ),
    # ----------------------------------------------------------
    # NOE
    # ----------------------------------------------------------
    "NOE": RegionTiming(
        frame3_offset=157,
        intro_pre_wait=1.0,
        intro_sequence=[
            # オーキド博士
            (0.1, 0.9),
            (0.1, 1.0),
            (0.1, 1.1),
            # ニドラン♀登場
            (0.1, 1.8),
            (0.1, 1.7),
            (0.1, 0.5),
            (0.1, 0.6),
            (0.1, 1.5),
            # ニドラン♀退場
            (0.1, 2.8),
            (0.1, 2.7),
        ],
        name_confirm_sequence=[
            # 名前決定
            (0.1, 2.5),
            (0.1, 2.8),
            # ライバル登場
            (0.1, 1.2),
            (0.1, 1.6),
        ],
        rival_confirm_sequence=[
            # 名前確定
            (0.1, 1.2),
            (0.1, 2.9),
            # 会話
            (0.1, 1.1),
            (0.1, 1.8),
        ],
        game_start_wait=6.5,
        report_a_presses=9,
        report_a_wait=1.5,
        tid_roi=(888, 86, 127, 47),
    ),
}
