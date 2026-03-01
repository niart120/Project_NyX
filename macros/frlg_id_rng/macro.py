"""
FRLG TID 乱数調整マクロ

ポケットモンスター ファイアレッド・リーフグリーンのニューゲーム開始時に
乱数を制御し、目標のトレーナーID (TID) を取得する自動化マクロ。
Switch (720p) 専用。
"""

from __future__ import annotations

import time

from nyxpy.framework.core.constants import Button, Hat
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command

from .frame_sweep import (
    dual_frame_sweep,
    frame_sweep,
    single_value_iterator,
)
from .keyboard_layout import (
    REGION_KEYBOARDS,
    RegionKeyboard,
    find_char_in_keyboard,
)
from .region_timing import REGION_TIMINGS, RegionTiming
from .tid_recognizer import recognize_tid

# ============================================================
# 定数
# ============================================================

_VALID_REGIONS = frozenset(REGION_TIMINGS.keys())
_TID_MAX = 65535


# ============================================================
# タイマーヘルパー (モジュールレベル — インスタンス状態を持たない)
# ============================================================


def _start_timer() -> float:
    """高精度タイマーの開始時刻を返す。"""
    return time.perf_counter()


def _consume_timer(
    cmd: Command, start_time: float, total_frames: float, fps: float
) -> None:
    """開始時刻からの経過時間を差し引き、残りフレーム分だけ待機する。

    :param cmd: コマンドインターフェース
    :param start_time: _start_timer() で取得した開始時刻
    :param total_frames: 待機すべき合計フレーム数
    :param fps: フレームレート
    """
    target_seconds = total_frames / fps
    elapsed = time.perf_counter() - start_time
    remaining = target_seconds - elapsed
    if remaining > 0:
        cmd.wait(remaining)


# ============================================================
# メインマクロクラス
# ============================================================


class FrlgIdRngMacro(MacroBase):
    """FRLG TID 乱数調整マクロ"""

    description = "FRLG TID乱数調整マクロ (Switch 720p)"
    tags = ["pokemon", "frlg", "rng", "tid"]

    # --------------------------------------------------------
    # ライフサイクル
    # --------------------------------------------------------

    def initialize(self, cmd: Command, args: dict) -> None:
        # --- 基本設定 ---
        self._region: str = str(args.get("region", "JPN"))
        if self._region not in _VALID_REGIONS:
            raise ValueError(
                f"未対応のリージョン: {self._region} (対応: {sorted(_VALID_REGIONS)})"
            )

        self._tid: int = int(args.get("tid", 0))
        if not 0 <= self._tid <= _TID_MAX:
            raise ValueError(f"tid は 0–{_TID_MAX} の範囲で指定してください: {self._tid}")

        self._trainer_name: str = str(args.get("trainer_name", "ナッツァ"))
        self._rival_name: str = str(args.get("rival_name", "グリーン"))
        self._default_rival_name: bool = bool(args.get("default_rival_name", False))
        self._gender: str = str(args.get("gender", "おとこのこ"))
        self._report_on_match: bool = bool(args.get("report_on_match", True))
        self._has_save_data: bool = bool(args.get("has_save_data", False))

        # --- フレームタイミング ---
        self._frame1: float = float(args.get("frame1", 1260))
        self._frame2: float = float(args.get("frame2", 1200))
        self._frame3_raw: float = float(args.get("frame3", 3009))
        self._op_frame: float = float(args.get("op_frame", 468))
        self._fps: float = float(args.get("fps", 60))

        # --- インクリメントモード ---
        self._frame_increment_mode: bool = bool(
            args.get("frame_increment_mode", False)
        )
        self._frame1_min: float = float(args.get("frame1_min", 1200))
        self._frame1_max: float = float(args.get("frame1_max", 1500))
        self._frame2_min: float = float(args.get("frame2_min", 1200))
        self._frame2_max: float = float(args.get("frame2_max", 1600))

        self._op_increment_mode: bool = bool(args.get("op_increment_mode", False))
        self._op_frame_min: float = float(args.get("op_frame_min", 382.0))
        self._op_frame_max: float = float(args.get("op_frame_max", 1000.0))

        self._id_tolerance_range: int = int(args.get("id_tolerance_range", 50))
        self._select_plus: int = int(args.get("select_plus", 0))

        # --- 派生値 ---
        self._timing: RegionTiming = REGION_TIMINGS[self._region]
        self._keyboard: RegionKeyboard = REGION_KEYBOARDS[self._region]
        self._frame3: float = self._frame3_raw - self._timing.frame3_offset

        cmd.log(
            f"FrlgIdRngMacro 初期化完了: region={self._region}, tid={self._tid}, "
            f"has_save_data={self._has_save_data}, "
            f"frame1={self._frame1}, frame2={self._frame2}, "
            f"frame3={self._frame3_raw}→{self._frame3} (offset={self._timing.frame3_offset}), "
            f"op_frame={self._op_frame}",
            level="INFO",
        )

    def run(self, cmd: Command) -> None:
        attempt = 0
        for current_f1, current_f2, current_op in self._build_iterator():
            attempt += 1
            cmd.log(
                f"--- {attempt}回目: Frame1={current_f1}, Frame2={current_f2}, OP={current_op} ---",
                level="INFO",
            )

            # Step 1: ソフトリセット
            self._soft_reset(cmd)

            # Step 2: OP待機 (内部でタイマー開始→操作→消化)
            self._wait_op(cmd, current_op)

            # Step 3: OP送り → ニューゲーム選択
            self._select_new_game(cmd)

            # --- Frame1 タイマー開始 ---
            t1 = _start_timer()
            cmd.press(Button.A, dur=0.1, wait=5.2)

            # Step 4: イントロ会話送り
            self._play_intro(cmd)

            # Step 5: 性別選択
            self._select_gender(cmd)

            # --- Frame1 タイマー消化 ---
            _consume_timer(cmd, t1, current_f1, self._fps)

            # --- Frame2 タイマー開始 ---
            t2 = _start_timer()

            # Step 7: 名前入力（主人公）
            self._enter_trainer_name(cmd)

            # --- Frame2 タイマー消化 ---
            _consume_timer(cmd, t2, current_f2, self._fps)

            # --- Frame3 タイマー開始 ---
            t3 = _start_timer()

            # Step 9: 名前決定後の会話進行
            self._press_a_sequence(
                cmd,
                self._timing.name_confirm_sequence,
                self._timing.name_confirm_sequence_no_save,
            )

            # Step 10: ライバル名前入力
            self._enter_rival_name(cmd)

            # Step 11: ライバル名確定後の会話
            self._press_a_sequence(
                cmd,
                self._timing.rival_confirm_sequence,
                self._timing.rival_confirm_sequence_no_save,
            )

            # --- Frame3 タイマー消化 ---
            _consume_timer(cmd, t3, self._frame3, self._fps)

            # Step 13: ゲーム開始（主人公の家へ）
            cmd.press(Button.A, dur=0.1, wait=self._timing.game_start_wait)

            cmd.log("ゲーム開始 TID チェック", level="INFO")
            # Step 14: TID 確認画面を開く
            self._open_trainer_card(cmd)

            # Step 15: TID 認識
            tid = self._recognize_tid(cmd)
            if tid is None:
                cmd.log("TID 認識失敗 — リトライ", level="WARNING")
                continue

            cmd.log(f"認識 TID: {tid:05d} (目標: {self._tid:05d})", level="INFO")

            # Step 16: TID 判定
            if self._check_tid(cmd, tid, attempt, current_f1, current_f2, current_op):
                return

        cmd.log("全探索範囲を走査完了 — 目標 TID 未発見", level="WARNING")

    def finalize(self, cmd: Command) -> None:
        cmd.release()
        cmd.log("FrlgIdRngMacro 終了", level="INFO")

    # --------------------------------------------------------
    # イテレータ構築
    # --------------------------------------------------------

    def _build_iterator(self):
        """設定に応じたフレーム探索イテレータを構築する。

        Yields: (frame1, frame2, op_frame)
        """
        if self._frame_increment_mode:
            frame_iter = dual_frame_sweep(
                self._frame1_min,
                self._frame1_max,
                self._frame2_min,
                self._frame2_max,
            )
            if self._op_increment_mode:
                # 両方インクリメント: OP を外側ループに
                for op in frame_sweep(self._op_frame_min, self._op_frame_max):
                    frame_iter = dual_frame_sweep(
                        self._frame1_min,
                        self._frame1_max,
                        self._frame2_min,
                        self._frame2_max,
                    )
                    for f1, f2 in frame_iter:
                        yield f1, f2, op
            else:
                for f1, f2 in frame_iter:
                    yield f1, f2, self._op_frame

        elif self._op_increment_mode:
            for op in frame_sweep(self._op_frame_min, self._op_frame_max):
                yield self._frame1, self._frame2, op

        else:
            # 固定値の無限イテレータ
            for _ in single_value_iterator(0):
                yield self._frame1, self._frame2, self._op_frame

    # --------------------------------------------------------
    # Step 実装
    # --------------------------------------------------------

    def _soft_reset(self, cmd: Command) -> None:
        """Step 1: ソフトリセット (A+B+X+Y 同時押し)"""
        cmd.press(Button.A, Button.B, Button.X, Button.Y, dur=0.30, wait=0.10)

    def _wait_op(self, cmd: Command, op_frame: float) -> None:
        """Step 2: OP待機 (タイマー開始→A操作→タイマー消化)"""
        t = _start_timer()
        cmd.press(Button.A, dur=0.20, wait=6.00)
        cmd.press(Button.A, dur=0.20, wait=0.0)
        _consume_timer(cmd, t, op_frame, self._fps)

    def _select_new_game(self, cmd: Command) -> None:
        """Step 3: OP送り → ニューゲーム選択 → ヘルプ画面通過

        セーブデータの有無でメニュー選択の操作が異なる:
        - あり: ↓ → A (メニュー2番目の「さいしょからはじめる」を選択)
        - なし: メニュー画面スキップで直接ヘルプ画面に飛ぶ
        いずれの場合もその後ヘルプ画面 (操作説明・ゲームの目的) を通過する。
        """
        # OPをAで飛ばす
        cmd.press(Button.A, dur=0.20, wait=0.167)
        cmd.press(Button.A, dur=0.20, wait=3.350)

        if self._has_save_data:
            # セーブデータあり: メニュー2番目の「さいしょからはじめる」を選択
            cmd.press(Hat.DOWN, dur=0.20, wait=0.335)
            cmd.press(Button.A, dur=0.1, wait=1.674)


        # ヘルプ画面: 操作方法の説明 (3回A) → 暗転 → ゲームプレイの目的 (3回A)
        # ヘルプ画面はセーブデータの有無にかかわらず常に表示される
        cmd.press(Button.A, dur=0.2, wait=1.0)
        cmd.press(Button.A, dur=0.2, wait=1.0)
        cmd.press(Button.A, dur=0.2, wait=2.5)

        cmd.press(Button.A, dur=0.2, wait=0.5)
        cmd.press(Button.A, dur=0.2, wait=0.5)
        cmd.press(Button.A, dur=0.2, wait=0.5)

    def _play_intro(self, cmd: Command) -> None:
        """Step 4: イントロ会話送り"""
        if self._timing.intro_pre_wait > 0:
            cmd.wait(self._timing.intro_pre_wait)
        self._press_a_sequence(
            cmd,
            self._timing.intro_sequence,
            self._timing.intro_sequence_no_save,
        )

    def _select_gender(self, cmd: Command) -> None:
        """Step 5: 性別選択"""
        if self._gender == "おんなのこ":
            cmd.press(Hat.DOWN, dur=0.1, wait=0.3)
        cmd.press(Button.A, dur=0.1, wait=2.5)

    def _enter_trainer_name(self, cmd: Command) -> None:
        """Step 7: 主人公の名前入力"""
        cmd.press(Button.A, dur=0.1, wait=1.5)
        self._enter_name(cmd, self._trainer_name, is_trainer=True)

    def _enter_rival_name(self, cmd: Command) -> None:
        """Step 10: ライバルの名前入力"""
        if self._default_rival_name:
            cmd.press(Hat.DOWN, dur=0.1, wait=0.3)
            cmd.press(Button.A, dur=0.1, wait=1.0)
        else:
            cmd.press(Button.A, dur=0.1, wait=1.5)
            self._enter_name(cmd, self._rival_name, is_trainer=False)
            cmd.press(Button.A, dur=0.1, wait=2.2)

    def _open_trainer_card(self, cmd: Command) -> None:
        """Step 14: メニュー → トレーナーカードを開く"""
        cmd.press(Button.PLUS, dur=0.10, wait=0.30)
        cmd.press(Hat.DOWN, dur=0.10, wait=0.20)
        cmd.press(Button.A, dur=0.10, wait=2.20)

    def _recognize_tid(self, cmd: Command) -> int | None:
        """Step 15: キャプチャして TID を OCR 認識"""
        image = cmd.capture()
        if image is None:
            return None
        return recognize_tid(image, self._timing.tid_roi)

    def _check_tid(
        self,
        cmd: Command,
        recognized_id: int,
        attempt: int,
        f1: float,
        f2: float,
        op: float,
    ) -> bool:
        """Step 16: TID 判定。完全一致なら True を返す。"""
        # --- 完全一致 ---
        if recognized_id == self._tid:
            msg = (
                f"{attempt}回目：目的のIDを引けました。"
                f"（Frame1：{f1}F、Frame2：{f2}F、OP待機：{op}F）"
            )
            cmd.log(msg, level="INFO")

            # キャプチャ保存 & 通知
            img = cmd.capture()
            if img is not None:
                cmd.save_img(f"frlg_tid_{recognized_id:05d}.png", img)
                cmd.notify(msg, img)
            else:
                cmd.notify(msg)

            # レポート書き込み
            if self._report_on_match:
                self._write_report(cmd)

            return True

        # --- インクリメントモードの許容範囲判定 ---
        if self._frame_increment_mode or self._op_increment_mode:
            if self._is_within_tolerance(recognized_id):
                msg = (
                    f"{attempt}回目：許容範囲内のIDを検出 (TID={recognized_id:05d})。"
                    f"（Frame1：{f1}F、Frame2：{f2}F、OP待機：{op}F）"
                )
                cmd.log(msg, level="INFO")
                img = cmd.capture()
                if img is not None:
                    cmd.save_img(
                        f"frlg_tid_{recognized_id:05d}_near.png", img
                    )
                    cmd.notify(msg, img)
                else:
                    cmd.notify(msg)

        return False

    # --------------------------------------------------------
    # 名前入力
    # --------------------------------------------------------

    def _enter_name(
        self, cmd: Command, name: str, *, is_trainer: bool = False
    ) -> None:
        """ソフトキーボードで名前を入力する。"""
        keyboard = self._keyboard
        cursor_x, cursor_y = 0, 0
        current_mode = 0

        for i, char in enumerate(name):
            target_char, need_dakuten, need_handakuten = self._resolve_char(
                char, keyboard
            )
            result = find_char_in_keyboard(keyboard, target_char)
            if result is None:
                cmd.log(
                    f"キーボードに文字 '{char}' が見つかりません — スキップ",
                    level="WARNING",
                )
                continue

            target_mode, tx, ty = result

            # モード切替 (Y ボタンで循環)
            while current_mode != target_mode:
                cmd.press(Button.Y, dur=0.2, wait=0.5)
                current_mode = (current_mode + 1) % len(keyboard.modes)

            # オフセット算出
            offset = 0
            if keyboard.compute_offset is not None:
                offset = keyboard.compute_offset(target_char, i)

            # カーソル移動 → 文字入力
            cursor_x, cursor_y = self._move_cursor(
                cmd, cursor_x, cursor_y, tx + offset, ty
            )
            cmd.press(Button.A, dur=0.2, wait=0.2)

            # 濁点処理
            if need_dakuten and keyboard.dakuten_pos is not None:
                cursor_x, cursor_y = self._move_cursor(
                    cmd, cursor_x, cursor_y, *keyboard.dakuten_pos
                )
                cmd.press(Button.A, dur=0.2, wait=0.2)

            # 半濁点処理
            if need_handakuten and keyboard.handakuten_pos is not None:
                cursor_x, cursor_y = self._move_cursor(
                    cmd, cursor_x, cursor_y, *keyboard.handakuten_pos
                )
                cmd.press(Button.A, dur=0.2, wait=0.2)

        # Select 操作 (主人公名入力時のみ)
        if is_trainer and self._select_plus > 0:
            for _ in range(self._select_plus):
                cmd.press(Button.Y, dur=0.2, wait=0.5)

        # START で名前確定
        cmd.press(Button.PLUS, dur=0.1, wait=0.5)

    @staticmethod
    def _resolve_char(
        char: str, keyboard: RegionKeyboard
    ) -> tuple[str, bool, bool]:
        """入力文字を (ベース文字, 濁点要否, 半濁点要否) に分解する。"""
        if keyboard.dakuten_map and char in keyboard.dakuten_map:
            return keyboard.dakuten_map[char], True, False
        if keyboard.handakuten_map and char in keyboard.handakuten_map:
            return keyboard.handakuten_map[char], False, True
        return char, False, False

    @staticmethod
    def _move_cursor(
        cmd: Command,
        cx: int,
        cy: int,
        tx: int,
        ty: int,
    ) -> tuple[int, int]:
        """カーソルを (cx, cy) → (tx, ty) へ1ステップずつ移動する。"""
        while cx != tx or cy != ty:
            if cx < tx:
                cmd.press(Hat.RIGHT, dur=0.1, wait=0.1)
                cx += 1
            elif cx > tx:
                cmd.press(Hat.LEFT, dur=0.1, wait=0.1)
                cx -= 1

            if cy < ty:
                cmd.press(Hat.DOWN, dur=0.1, wait=0.1)
                cy += 1
            elif cy > ty:
                cmd.press(Hat.UP, dur=0.1, wait=0.1)
                cy -= 1

        return cx, cy

    # --------------------------------------------------------
    # レポート書き込み
    # --------------------------------------------------------

    def _write_report(self, cmd: Command) -> None:
        """ゲーム内レポート（セーブ）を実行する。"""
        cmd.wait(1.0)
        cmd.press(Button.B, dur=0.10, wait=2.00)
        cmd.press(Hat.DOWN, dur=0.10, wait=0.50)
        for _ in range(self._timing.report_a_presses):
            cmd.press(Button.A, dur=0.10, wait=self._timing.report_a_wait)
        cmd.press(Hat.UP, dur=0.10, wait=0.30)
        cmd.press(Button.A, dur=0.10, wait=8.50)

    # --------------------------------------------------------
    # ユーティリティ
    # --------------------------------------------------------

    def _press_a_sequence(
        self,
        cmd: Command,
        sequence: list[tuple[float, float]],
        no_save_sequence: list[tuple[float, float]] | None = None,
    ) -> None:
        """A ボタンの (dur, wait) シーケンスを順に実行する。

        ``has_save_data=False`` かつ ``no_save_sequence`` が指定されている場合は
        ``no_save_sequence`` を使用する。
        ``no_save_sequence`` が ``None`` の場合は ``sequence`` を使用する。
        """
        seq = (
            no_save_sequence
            if not self._has_save_data and no_save_sequence is not None
            else sequence
        )
        for dur, wait in seq:
            cmd.press(Button.A, dur=dur, wait=wait)

    def _is_within_tolerance(self, recognized_id: int) -> bool:
        """インクリメントモード時の許容範囲判定 (TID は 0–65535 で循環)。"""
        lower = self._tid - self._id_tolerance_range
        upper = self._tid + self._id_tolerance_range

        if lower < 0:
            lower += _TID_MAX + 1
        if upper > _TID_MAX:
            upper -= _TID_MAX + 1

        if lower <= upper:
            return lower <= recognized_id <= upper
        else:
            # 範囲が 0 を跨ぐ場合
            return recognized_id >= lower or recognized_id <= upper
