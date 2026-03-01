"""
FRLG ソフトリセットマクロ

A+B+X+Y を同時押しして Nintendo Switch のゲームをソフトリセットする。
"""

from __future__ import annotations

from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command


class FrlgSoftResetMacro(MacroBase):
    """FRLG ソフトリセット専用マクロ"""

    description = "FRLG ソフトリセット (A+B+X+Y 同時押し)"
    tags = ["pokemon", "frlg", "reset"]

    def initialize(self, cmd: Command, args: dict) -> None:
        self._repeat: int = int(args.get("repeat", 1))
        self._press_dur: float = float(args.get("press_dur", 0.30))
        self._wait_dur: float = float(args.get("wait_dur", 0.10))

        if self._repeat <= 0:
            raise ValueError(f"repeat は 1 以上で指定してください: {self._repeat}")
        if self._press_dur < 0 or self._wait_dur < 0:
            raise ValueError("press_dur / wait_dur は 0 以上で指定してください")

        cmd.log(
            f"FrlgSoftResetMacro 初期化完了: repeat={self._repeat}, "
            f"press_dur={self._press_dur}, wait_dur={self._wait_dur}",
            level="INFO",
        )

    def run(self, cmd: Command) -> None:
        for i in range(1, self._repeat + 1):
            cmd.log(f"ソフトリセット {i}/{self._repeat}", level="INFO")
            cmd.press(
                Button.A, Button.B, Button.X, Button.Y,
                dur=self._press_dur,
                wait=self._wait_dur,
            )

    def finalize(self, cmd: Command) -> None:
        cmd.release()
        cmd.log("FrlgSoftResetMacro 終了", level="INFO")
