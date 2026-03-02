"""
FRLG 初期Seed特定マクロ

ゲームのソフトリセット → 捕獲 → OCR で性格・実数値を取得し
16bit 初期Seed を逆算して CSV に記録するマクロ。
Switch (720p) 専用。
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

import cv2
import numpy as np

from nyxpy.framework.core.constants import Button, LStick
from nyxpy.framework.core.imgproc import OCRProcessor
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command

from .config import FrlgInitialSeedConfig
from .recognizer import (
    ROI_NATURE,
    ROI_STATS,
    get_nature_text,
    get_stat_digits,
    recognize_nature,
    recognize_stats,
)
from .seed_solver import solve_initial_seed

# ステータス ROI に対応するファイル名サフィックス
_STAT_FILE_NAMES: tuple[str, ...] = ("hp", "atk", "def", "spa", "spd", "spe")
_ROI_PADDING: int = 40


# ============================================================
# 型エイリアス
# ============================================================

# 1 trial の結果: (seed 文字列, advance or None)
TrialResult = tuple[str, int | None]

# 1 フレーム分の CSV 行データ
FrameRow = dict[str, list[str]]  # {"seeds": [...], "advances": [...]}


# ============================================================
# タイマーヘルパー
# ============================================================


def _start_timer() -> float:
    """高精度タイマーの開始時刻を返す。"""
    return time.perf_counter()


def _consume_timer(
    cmd: Command, start_time: float, total_frames: float, fps: float
) -> None:
    """開始時刻からの経過時間を差し引き、残りフレーム分だけ待機する。"""
    target_seconds = total_frames / fps
    elapsed = time.perf_counter() - start_time
    remaining = target_seconds - elapsed
    if remaining > 0:
        cmd.wait(remaining)
    elif remaining < -0.5:
        cmd.log(
            f"タイマー超過: {-remaining:.3f}秒 (操作が指定フレーム数を超過)",
            level="WARNING",
        )


# ============================================================
# CSV ヘルパー
# ============================================================

_CSV_HEADER_PREFIX = ["frame"]


def _build_csv_path(cfg: FrlgInitialSeedConfig) -> Path:
    """CSV ファイルパスを構築する。"""
    return Path(cfg.output_dir) / f"{cfg.file_name}.csv"


def _new_frame_row(trials: int) -> FrameRow:
    """空の FrameRow を生成する。"""
    return {"seeds": [""] * trials, "advances": [""] * trials}


def _load_csv(
    csv_path: Path, trials: int
) -> tuple[dict[int, FrameRow], int | None]:
    """既存 CSV を読み込み、フレーム → FrameRow の dict を返す。

    Returns:
        (data, resume_frame)
        data: {frame: {"seeds": [...], "advances": [...]}}
        resume_frame: 測定が trials 回に満たない最初のフレーム、なければ None
    """
    data: dict[int, FrameRow] = {}
    resume_frame: int | None = None

    if not csv_path.exists():
        return data, resume_frame

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame = int(row["frame"])
            seeds = [row.get(f"seed_{i}", "") for i in range(1, trials + 1)]
            advances = [row.get(f"adv_{i}", "") for i in range(1, trials + 1)]
            data[frame] = {"seeds": seeds, "advances": advances}

            # 最初の未完了フレームを記録
            if resume_frame is None:
                filled = sum(1 for s in seeds if s)
                if filled < trials:
                    resume_frame = frame

    return data, resume_frame


def _save_csv(
    csv_path: Path,
    data: dict[int, FrameRow],
    cfg: FrlgInitialSeedConfig,
) -> None:
    """CSV を書き出す。"""
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    seed_columns = [f"seed_{i}" for i in range(1, cfg.trials + 1)]
    adv_columns = [f"adv_{i}" for i in range(1, cfg.trials + 1)]
    fieldnames = _CSV_HEADER_PREFIX + seed_columns + adv_columns

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for frame in sorted(data.keys()):
            frame_row = data[frame]
            seeds = frame_row["seeds"]
            advances = frame_row["advances"]

            row: dict[str, str] = {
                "frame": str(frame),
            }
            for i, col in enumerate(seed_columns):
                row[col] = seeds[i] if i < len(seeds) else ""
            for i, col in enumerate(adv_columns):
                row[col] = advances[i] if i < len(advances) else ""
            writer.writerow(row)


# ============================================================
# メインマクロクラス
# ============================================================


class FrlgInitialSeedMacro(MacroBase):
    """FRLG 初期Seed特定マクロ (Switch 720p)"""

    description = "FRLG 初期Seed特定マクロ (Switch 720p)"
    tags = ["pokemon", "frlg", "rng", "seed"]

    _MAX_RETRIES: int = 3
    """1 trial あたりの認識リトライ上限"""

    # --------------------------------------------------------
    # ライフサイクル
    # --------------------------------------------------------

    def initialize(self, cmd: Command, args: dict) -> None:
        self._cfg = FrlgInitialSeedConfig.from_args(args)
        cfg = self._cfg

        cmd.log(
            f"FrlgInitialSeedMacro 初期化完了: "
            f"min_frame={cfg.min_frame}, max_frame={cfg.max_frame}, "
            f"trials={cfg.trials}, frame2={cfg.frame2}, "
            f"min_advance={cfg.min_advance}, max_advance={cfg.max_advance}, "
            f"fps={cfg.fps}",
            level="INFO",
        )

        # デバッグ画像保存先を確保
        self._img_dir = Path(cfg.output_dir) / "img"
        self._img_dir.mkdir(parents=True, exist_ok=True)
        cmd.log(f"デバッグ画像保存先: {self._img_dir}", level="DEBUG")

        # CSV 読み込み・再開ポイント算出
        self._csv_path = _build_csv_path(cfg)
        self._csv_data, resume = _load_csv(self._csv_path, cfg.trials)

        if resume is not None:
            self._start_frame = resume
            cmd.log(f"既存 CSV を検出 — Frame {resume} から再開", level="INFO")
        elif self._csv_data:
            last = max(self._csv_data.keys())
            self._start_frame = last + 1
            cmd.log(
                f"既存 CSV は全フレーム完了済み — Frame {self._start_frame} から続行",
                level="INFO",
            )
        else:
            self._start_frame = cfg.min_frame
            cmd.log(f"新規開始 — Frame {cfg.min_frame}", level="INFO")

        # OCR ウォームアップ
        cmd.log("OCR ウォームアップ開始", level="INFO")
        ocr = OCRProcessor.get_instance("ja")
        try:
            ocr.get_best_text(np.zeros((64, 200, 3), dtype=np.uint8))
        except Exception:
            pass
        cmd.log("OCR ウォームアップ完了", level="INFO")

    def run(self, cmd: Command) -> None:
        cfg = self._cfg

        for frame1 in range(self._start_frame, cfg.max_frame + 1):
            frame_label = frame1 + cfg.frame1_offset
            self._ensure_frame_row(frame_label)
            frame_row = self._csv_data[frame_label]

            start_trial = sum(1 for s in frame_row["seeds"] if s)

            for trial in range(start_trial, cfg.trials):
                cmd.log(
                    f"--- Frame {frame_label} ({trial + 1}/{cfg.trials}) ---",
                    level="INFO",
                )

                seed_result, advance = self._run_trial_with_retry(cmd, frame1)

                frame_row["seeds"][trial] = seed_result
                frame_row["advances"][trial] = (
                    str(advance) if advance is not None else ""
                )
                _save_csv(self._csv_path, self._csv_data, cfg)

                adv_str = str(advance) if advance is not None else "-"
                cmd.log(
                    f"{frame_label}F ({trial + 1}/{cfg.trials})"
                    f"：{seed_result} (adv={adv_str})",
                    level="INFO",
                )

        # 完了通知
        self._notify_completion(cmd)

    def finalize(self, cmd: Command) -> None:
        cmd.release()
        cmd.log("FrlgInitialSeedMacro 終了", level="INFO")

    # --------------------------------------------------------
    # trial ループ
    # --------------------------------------------------------

    def _run_trial_with_retry(
        self, cmd: Command, frame1: int
    ) -> TrialResult:
        """1 trial を実行し、認識失敗時は最大 _MAX_RETRIES 回まで再試行する。

        リトライ時も frame2 は設定値のまま変更しない。
        リトライ上限を超えた場合は ("False", None) として記録する。
        """
        cfg = self._cfg

        for attempt in range(1, self._MAX_RETRIES + 1):
            result = self._run_single_trial(cmd, frame1, cfg.frame2)
            if result is not None:
                return result
            cmd.log(
                f"認識失敗 ({attempt}/{self._MAX_RETRIES}) — リトライ",
                level="WARNING",
            )

        cmd.log("リトライ上限到達 — False として記録", level="WARNING")
        return ("False", None)

    # --------------------------------------------------------
    # 1回分の試行 (ゲーム再起動 〜 Seed 逆算)
    # --------------------------------------------------------

    def _run_single_trial(
        self, cmd: Command, frame1: int, frame2: int
    ) -> TrialResult | None:
        """1 回分の試行を実行する。

        Returns:
            (Seed 文字列, advance) または認識失敗時は None。
        """
        cfg = self._cfg

        # === Phase 1: ゲーム再起動 → タイマー制御 → エンカウント ===
        cmd.log("Phase1: ゲーム再起動", level="DEBUG")
        self._restart_game(cmd)

        cmd.log("Phase1: frame1 タイマー消化", level="DEBUG")
        _consume_timer(cmd, self._t1, frame1 + cfg.frame1_offset, cfg.fps)

        t2 = _start_timer()
        cmd.log("Phase1: OP送り → つづきから → 回想スキップ", level="DEBUG")
        self._navigate_to_encounter(cmd)

        cmd.log("Phase1: frame2 タイマー消化", level="DEBUG")
        _consume_timer(cmd, t2, frame2 + cfg.frame2_offset, cfg.fps)

        cmd.log("Phase1: エンカウント発生", level="DEBUG")
        self._trigger_encounter(cmd)

        # === Phase 2: 捕獲 → B 連打 → ステータス画面表示 ===
        cmd.log("Phase2: 捕獲操作", level="DEBUG")
        self._capture_pokemon(cmd)

        cmd.log("Phase2: 捕獲後ダイアログ B 連打", level="DEBUG")
        self._dismiss_post_capture(cmd)

        cmd.log("Phase2: ステータス画面を開く", level="DEBUG")
        self._open_status_screen(cmd)

        # === Phase 3: OCR 認識 → Seed 逆算 ===
        cmd.log("Phase3: OCR 認識 → Seed 逆算", level="DEBUG")
        return self._recognize_and_solve(cmd)

    # --------------------------------------------------------
    # Phase 1: ゲーム操作
    # --------------------------------------------------------

    def _restart_game(self, cmd: Command) -> None:
        """ゲームを終了→再起動し、frame1 タイマーを開始する。"""
        cmd.press(Button.HOME, dur=0.15, wait=0.50)
        cmd.press(Button.X, dur=0.20, wait=0.30)
        cmd.press(Button.A, dur=0.20, wait=0.50)
        cmd.press(Button.A, dur=0.20, wait=0.50)
        self._t1 = _start_timer()
        cmd.press(Button.A, dur=0.20)  # ゲーム起動

    def _navigate_to_encounter(self, cmd: Command) -> None:
        """OP送り → つづきからはじめる → 回想スキップ。

        frame2 タイマーの計測区間内で実行される操作。
        所要時間はタイマーにより自然に吸収される。
        """
        cmd.press(Button.A, dur=3.50, wait=1.00)   # OP を A で飛ばす
        cmd.press(Button.A, dur=0.20, wait=1.50)   # つづきからはじめる
        cmd.press(Button.B, dur=0.50, wait=2.00)   # 回想を B で飛ばす

    def _trigger_encounter(self, cmd: Command) -> None:
        """ルギアに話しかけてエンカウントを発生させる。"""
        cmd.press(Button.A, dur=0.10, wait=11.00)   # 話しかける → エンカウント
        cmd.press(Button.A, dur=0.10, wait=3.00)   # メッセージ送り(ルギアが あらわれた！)

    # --------------------------------------------------------
    # Phase 2: 捕獲 → ステータス表示
    # --------------------------------------------------------

    def _capture_pokemon(self, cmd: Command) -> None:
        """マスターボールで捕獲する。

        操作手順: → A → → → A(マスターボール選択) A(つかう) [捕獲完了待機]
        """
        cmd.press(LStick.RIGHT, dur=0.10, wait=0.30)   # 「バッグ」を選択
        cmd.press(Button.A, dur=0.10, wait=1.20)     # バッグを開く
        cmd.press(LStick.RIGHT, dur=0.10, wait=0.50)  # ポケット移動
        cmd.press(LStick.RIGHT, dur=0.10, wait=0.50)  # ポケット移動
        cmd.press(Button.A, dur=0.10, wait=0.30)    # マスターボールを選択
        cmd.press(Button.A, dur=0.10, wait=8.00)    # 「つかう」→ 捕獲アニメーション

    def _dismiss_post_capture(self, cmd: Command) -> None:
        """捕獲後のダイアログを B ボタン連打で処理する。

        図鑑登録・ニックネーム確認・戦闘終了など一連のダイアログを
        すべて B で送る。約 10 秒間。
        """
        for _ in range(50):  # 10 秒間 B を連打
            cmd.press(Button.B, dur=0.10, wait=0.10)

    def _open_status_screen(self, cmd: Command) -> None:
        """メニューからステータス画面を開く。"""
        cmd.press(Button.PLUS, dur=0.10, wait=0.30) # メニューを開く
        cmd.press(LStick.DOWN, dur=0.10, wait=0.10)    # カーソルを移動
        cmd.press(Button.A, dur=0.10, wait=1.20)    # ポケモンを選択
        cmd.press(LStick.UP, dur=0.10, wait=0.10)    # カーソルを移動
        cmd.press(LStick.UP, dur=0.10, wait=0.10)    # カーソルを移動
        cmd.press(Button.A, dur=0.10, wait=0.30)    # ルギアを選択
        cmd.press(Button.A, dur=0.10, wait=0.30)    # 「つよさをみる」
        cmd.press(Button.A, dur=0.10, wait=2.40)    # ステータス画面表示

    # --------------------------------------------------------
    # Phase 3: OCR 認識 → Seed 逆算
    # --------------------------------------------------------

    def _recognize_and_solve(self, cmd: Command) -> TrialResult | None:
        """性格・ステータスを OCR 認識し、Seed 逆算を実行する。

        性格による足切りは行うが、性格・ステータスの取得自体は常に
        両方実行する。認識失敗時は None を返す。
        """
        cfg = self._cfg

        # --- 性格画面キャプチャ → ROI 保存 → 認識 ---
        image = cmd.capture()
        if image is None:
            cmd.log("キャプチャ失敗", level="WARNING")
            return None

        self._save_roi_image(image, ROI_NATURE, "nature.png")

        nature_raw = get_nature_text(image)
        cmd.log(f"OCR生文字列(性格): {nature_raw!r}", level="DEBUG")

        nature = recognize_nature(image)
        if nature is None:
            cmd.log("性格認識失敗", level="WARNING")
        else:
            cmd.log(f"性格認識: {nature}", level="INFO")

        # --- 実数値画面に切替 → ROI 保存 → 認識（性格認識の成否に依らず常に実行）---
        cmd.press(LStick.RIGHT, dur=0.10, wait=1.00)

        stat_image = cmd.capture()
        if stat_image is None:
            cmd.log("キャプチャ失敗（実数値）", level="WARNING")
            return None

        for roi, name in zip(ROI_STATS, _STAT_FILE_NAMES):
            self._save_roi_image(stat_image, roi, f"stat_{name}.png")

        stat_raw = get_stat_digits(stat_image)
        cmd.log(
            "OCR生文字列(ステータス): "
            f"HP={stat_raw[0]!r}, Atk={stat_raw[1]!r}, Def={stat_raw[2]!r}, "
            f"SpA={stat_raw[3]!r}, SpD={stat_raw[4]!r}, Spe={stat_raw[5]!r}",
            level="DEBUG",
        )

        stats = recognize_stats(stat_image)
        if stats is None:
            cmd.log("ステータス認識失敗", level="WARNING")
        else:
            cmd.log(
                f"ステータス認識: HP={stats[0]}, Atk={stats[1]}, Def={stats[2]}, "
                f"SpA={stats[3]}, SpD={stats[4]}, Spe={stats[5]}",
                level="INFO",
            )

        # ステータス認識失敗時は逆算不可（性格は None でも続行）
        if stats is None:
            return None

        # Seed 逆算（性格が None の場合はステータスのみで照合）
        if nature is None:
            cmd.log("性格不明のためステータスのみで Seed 逆算開始", level="INFO")
        else:
            cmd.log("Seed 逆算開始", level="DEBUG")
        seed, advance = solve_initial_seed(
            nature=nature,
            observed_stats=stats,
            base_stats=cfg.base_stats,
            level=cfg.level,
            min_advance=cfg.min_advance,
            max_advance=cfg.max_advance,
        )
        cmd.log(f"Seed 逆算完了: seed={seed}, advance={advance}", level="DEBUG")
        return (seed, advance)

    # --------------------------------------------------------
    # ユーティリティ
    # --------------------------------------------------------

    def _ensure_frame_row(self, frame_label: int) -> None:
        """CSV データに当該フレームの行を確保する。"""
        if frame_label not in self._csv_data:
            self._csv_data[frame_label] = _new_frame_row(self._cfg.trials)

    def _save_roi_image(
        self,
        image: np.ndarray,
        roi: tuple[int, int, int, int],
        filename: str,
    ) -> None:
        """ROI をクロップし白パディングを付与して保存する（毎回上書き）。

        frlg_id_rng の TID ROI 保存と同様のパターン。
        """
        x, y, w, h = roi
        cropped = image[y : y + h, x : x + w]
        padded = cv2.copyMakeBorder(
            cropped,
            _ROI_PADDING,
            _ROI_PADDING,
            _ROI_PADDING,
            _ROI_PADDING,
            borderType=cv2.BORDER_CONSTANT,
            value=(255, 255, 255),
        )
        path = self._img_dir / filename
        cv2.imwrite(str(path), padded)

    def _notify_completion(self, cmd: Command) -> None:
        """完了通知を送信する。"""
        cfg = self._cfg
        msg = (
            f"[FRLG初期Seed集め自動化] "
            f"初期Seedを{cfg.max_frame}Fまで取得したので、プログラムを終了します。"
        )
        cmd.log(msg, level="INFO")
        image = cmd.capture()
        if image is not None:
            cmd.notify(msg, image)
        else:
            cmd.notify(msg)
