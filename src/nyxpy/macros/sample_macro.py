from nyxpy.framework.core.macro.base import MacroBase
from nyxpy.framework.core.macro.command import Command
from nyxpy.framework.core.macro.constants import Button

class SampleMacro(MacroBase):
    def initialize(self, cmd: Command, args: dict) -> None:
        cmd.log("SampleMacro: Initialization started.", level="INFO")
        # You can process macro arguments from 'args' here.
        self.args = args

    def run(self, cmd: Command) -> None:
        cmd.log("SampleMacro: Running macro.", level="INFO")
        # Simulate a button press operation.
        cmd.press(Button.A, dur=0.2, wait=0.1)
        # Send a sample keyboard input.
        cmd.keyboard("Hello from SampleMacro!")
        # Attempt to capture the screen.
        frame = cmd.capture()
        if frame is not None:
            # Save the captured frame.
            cmd.save_img("sample_macro_screenshot.png", frame)
            cmd.log("SampleMacro: Screen captured and saved.", level="DEBUG")
        else:
            cmd.log("SampleMacro: Capture failed.", level="ERROR")

    def finalize(self, cmd: Command) -> None:
        # Ensure the button is released.
        cmd.release()
        cmd.log("SampleMacro: Finalization completed.", level="INFO")
