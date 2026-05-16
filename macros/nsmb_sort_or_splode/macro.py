import cv2

from nyxpy.framework.core.constants import THREEDS_HD_BOTTOM_SCREEN, TouchPoint
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command

from .config import NsmbSortOrSplodeConfig
from .recognizer import (
    BombColor,
    DetectedBomb,
    build_drag_path,
    classify_bombs,
    find_bombs,
    paint_ignored_rects,
)


class NsmbSortOrSplodeMacro(MacroBase):
    macro_id = "nsmb_sort_or_splode"
    display_name = "NSMB Sort or 'Splode"
    description = "NSMB Sort or 'Splode（ボムへいをわけろ）自動仕分けマクロ"
    tags = ["nsmb", "3ds", "touch", "image-recognition"]
    settings_path = "project:resources/nsmb_sort_or_splode/settings.toml"

    def initialize(self, cmd: Command, args: dict) -> None:
        self._cfg = NsmbSortOrSplodeConfig.from_args(args)
        self._red_template = cmd.load_img(self._cfg.red_template_path)
        self._black_template = cmd.load_img(self._cfg.black_template_path)
        self._sorted_count = 0
        self._finished = False
        cmd.log(
            "NSMB Sort or 'Splode initialized: "
            f"red_template={self._red_template.shape}, "
            f"black_template={self._black_template.shape}",
            level="INFO",
        )

    def run(self, cmd: Command) -> None:
        while not self._finished:
            self.run_iteration(cmd)
            if self._cfg.scan_interval_seconds > 0 and not self._finished:
                cmd.wait(self._cfg.scan_interval_seconds)

    def finalize(self, cmd: Command) -> None:
        pass

    def run_iteration(self, cmd: Command) -> DetectedBomb | None:
        frame = cmd.capture(crop_region=THREEDS_HD_BOTTOM_SCREEN.tuple)
        if frame is None:
            raise RuntimeError("capture failed")
        if frame.shape[:2] != (THREEDS_HD_BOTTOM_SCREEN.height, THREEDS_HD_BOTTOM_SCREEN.width):
            raise RuntimeError(f"unexpected bottom screen shape: {frame.shape}")

        masked = paint_ignored_rects(
            frame,
            self._cfg.ignore_touch_rects,
            fill_bgr=self._cfg.mask_fill_bgr,
        )
        red_candidates = find_bombs(
            masked,
            self._red_template,
            color=BombColor.RED,
            threshold=self._cfg.red_match_threshold,
            duplicate_suppression_radius=self._cfg.duplicate_suppression_radius,
        )
        black_candidates = find_bombs(
            masked,
            self._black_template,
            color=BombColor.BLACK,
            threshold=self._cfg.black_match_threshold,
            duplicate_suppression_radius=self._cfg.duplicate_suppression_radius,
        )
        candidates = classify_bombs(
            frame,
            red_candidates,
            black_candidates,
            red_threshold=self._cfg.red_match_threshold,
            black_threshold=self._cfg.black_match_threshold,
            duplicate_suppression_radius=self._cfg.duplicate_suppression_radius,
            template_score_margin=self._cfg.template_score_margin,
            color_sample_size=self._cfg.color_sample_size,
            red_min_ratio=self._cfg.red_min_ratio,
            black_min_dark_ratio=self._cfg.black_min_dark_ratio,
            black_max_red_ratio=self._cfg.black_max_red_ratio,
        )
        if not candidates:
            return None

        bomb = candidates[0]
        goal = (
            self._cfg.red_goal_touch if bomb.color is BombColor.RED else self._cfg.black_goal_touch
        )
        self._drag(cmd, bomb.touch_point, goal)
        self._sorted_count += 1
        if self._cfg.save_debug_frames:
            self._save_debug_frame(cmd, masked, bomb, goal)
        if self._cfg.post_drop_wait_seconds > 0:
            cmd.wait(self._cfg.post_drop_wait_seconds)
        if self._cfg.max_sorted_count > 0 and self._sorted_count >= self._cfg.max_sorted_count:
            self._finished = True
            if self._cfg.notify_on_finish:
                cmd.notify(f"Sort or 'Splode: {self._sorted_count} 個仕分けて終了")
        return bomb

    def _drag(self, cmd: Command, start: TouchPoint, goal: TouchPoint) -> None:
        path = build_drag_path(start, goal, steps=self._cfg.drag_steps)
        wait_per_step = self._cfg.drag_duration_seconds / self._cfg.drag_steps
        touch_started = False
        try:
            for point in path:
                cmd.touch_down(point.x, point.y)
                touch_started = True
                if wait_per_step > 0:
                    cmd.wait(wait_per_step)
        finally:
            if touch_started:
                cmd.touch_up()

    def _save_debug_frame(
        self,
        cmd: Command,
        frame,
        bomb: DetectedBomb,
        goal: TouchPoint,
    ) -> None:
        debug = frame.copy()
        cropped_x = bomb.hd_center_x - THREEDS_HD_BOTTOM_SCREEN.x
        cropped_y = bomb.hd_center_y - THREEDS_HD_BOTTOM_SCREEN.y
        cv2.circle(debug, (cropped_x, cropped_y), 8, (255, 0, 255), thickness=2)
        goal_hd_x = round(goal.x * THREEDS_HD_BOTTOM_SCREEN.width / 320)
        goal_hd_y = round(goal.y * THREEDS_HD_BOTTOM_SCREEN.height / 240)
        cv2.line(debug, (cropped_x, cropped_y), (goal_hd_x, goal_hd_y), (255, 0, 255), 2)
        cmd.save_img(
            f"nsmb_sort_or_splode/debug_{self._sorted_count:04d}_{bomb.color}.png",
            debug,
        )
