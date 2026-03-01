from nyxpy.framework.core.constants import Button
from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command


class SampleTurboAMacro(MacroBase):
    description = "Aボタンを一定回数連打し、必要に応じてキャプチャを保存するサンプル"
    tags = ["sample", "basic", "button"]

    def initialize(self, cmd: Command, args: dict) -> None:
        self.count = int(args.get("count", 20))
        self.press_dur = float(args.get("press_dur", 0.06))
        self.wait_dur = float(args.get("wait_dur", 0.08))
        self.capture_after = bool(args.get("capture_after", True))
        self.capture_name = str(args.get("capture_name", "sample_turbo_a_result.png"))

        if self.count <= 0:
            raise ValueError("count must be greater than 0")
        if self.press_dur < 0 or self.wait_dur < 0:
            raise ValueError("press_dur and wait_dur must be non-negative")

        cmd.log(
            f"SampleTurboAMacro initialized: count={self.count}, press_dur={self.press_dur}, wait_dur={self.wait_dur}, capture_after={self.capture_after}"
        )

    def run(self, cmd: Command) -> None:
        for index in range(1, self.count + 1):
            cmd.press(Button.A, dur=self.press_dur, wait=self.wait_dur)
            if index % 5 == 0:
                cmd.log(f"Progress: {index}/{self.count}")

        if self.capture_after:
            frame = cmd.capture()
            if frame is not None:
                cmd.save_img(self.capture_name, frame)
                cmd.notify(f"SampleTurboAMacro complete: saved {self.capture_name}", frame)
            else:
                cmd.notify("SampleTurboAMacro complete: capture failed")

    def finalize(self, cmd: Command) -> None:
        cmd.release()
        cmd.log("SampleTurboAMacro finalized")
