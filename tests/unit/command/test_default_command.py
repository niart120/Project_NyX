import time
import pytest
from nyxpy.framework.core.macro.command import DefaultCommand
from nyxpy.framework.core.macro.constants import Button

# Mock for HardwareFacade
class MockHardwareFacade:
    def __init__(self):
        self.sent_data = []
        self.captured = False

    def send(self, data):
        self.sent_data.append(data)

    def capture(self):
        self.captured = True
        return self._frame if hasattr(self, "_frame") else None

# Mock for ResourceIO
class MockResourceIO:
    def __init__(self):
        self.saved_images = {}

    def save_image(self, filename, image):
        self.saved_images[filename] = image

    def load_image(self, filename, grayscale=False):
        return self.saved_images.get(filename, None)

# Mock for Protocol
class MockProtocol:
    def __init__(self):
        self.calls = []

    def build_press_command(self, keys):
        self.calls.append(('press', keys))
        return b'press:' + b'-'.join(str(k).encode() for k in keys)

    def build_release_command(self, keys):
        self.calls.append(('release', keys))
        return b'release:' + b'-'.join(str(k).encode() for k in keys)

    def build_keyboard_command(self, text):
        self.calls.append(('keyboard', text))
        return b'keyboard:' + text.encode()

# Mock for CancellationToken
class MockCancellationToken:
    def __init__(self):
        self.stopped = False

    def request_stop(self):
        self.stopped = True
    
    def stop_requested(self):
        return self.stopped

@pytest.fixture
def dummy_command(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda x: None)
    hardware_facade = MockHardwareFacade()
    resource_io = MockResourceIO()
    protocol = MockProtocol()
    ct = MockCancellationToken()
    cmd = DefaultCommand(
        hardware_facade=hardware_facade,
        resource_io=resource_io,
        protocol=protocol,
        ct=ct
    )
    return cmd, hardware_facade, resource_io, protocol, ct

def test_press_and_release(dummy_command):
    cmd, hardware_facade, resource_io, protocol, ct = dummy_command
    cmd.press(Button.A, Button.B, dur=0.2, wait=0.1)
    assert protocol.calls[0][0] == 'press'
    assert protocol.calls[1][0] == 'release'
    assert hardware_facade.sent_data[0].startswith(b'press:')
    assert hardware_facade.sent_data[1].startswith(b'release:')

def test_hold(dummy_command):
    cmd, hardware_facade, resource_io, protocol, ct = dummy_command
    cmd.hold(Button.X)
    assert protocol.calls[0][0] == 'press'
    assert hardware_facade.sent_data[0].startswith(b'press:')

def test_release(dummy_command):
    cmd, hardware_facade, resource_io, protocol, ct = dummy_command
    cmd.release(Button.Y)
    assert protocol.calls[0][0] == 'release'
    assert hardware_facade.sent_data[0].startswith(b'release:')

def test_wait(dummy_command):
    cmd, *_ = dummy_command
    start = time.time()
    cmd.wait(0.5)
    end = time.time()
    assert end - start < 0.1  # monkeypatchで即時

def test_stop(dummy_command):
    cmd, _, _, _, ct = dummy_command
    with pytest.raises(Exception):
        cmd.stop()
    assert ct.stopped

def test_keyboard(dummy_command):
    cmd, hardware_facade, resource_io, protocol, ct = dummy_command
    cmd.keyboard("Hello")
    assert protocol.calls[0][0] == 'keyboard'
    assert hardware_facade.sent_data[0].startswith(b'keyboard:')

def test_save_img_and_load_img(dummy_command):
    cmd, _, resource_io, _, _ = dummy_command
    dummy_img = b"img"
    cmd.save_img("foo.png", dummy_img)
    assert resource_io.saved_images["foo.png"] == dummy_img
    loaded = cmd.load_img("foo.png")
    assert loaded == dummy_img

def test_capture_success(monkeypatch, dummy_command):
    cmd, hardware_facade, _, _, _ = dummy_command
    import numpy as np
    # 1280x720x3 のダミーフレーム
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    hardware_facade._frame = dummy_frame
    result = cmd.capture()
    assert result.shape == (720, 1280, 3)

def test_capture_crop_and_gray(monkeypatch, dummy_command):
    cmd, hardware_facade, _, _, _ = dummy_command
    import numpy as np
    dummy_frame = np.ones((720, 1280, 3), dtype=np.uint8) * 255
    hardware_facade._frame = dummy_frame
    # クロップ領域指定
    crop = (100, 100, 200, 200)
    result = cmd.capture(crop_region=crop, grayscale=True)
    assert result.shape == (200, 200)
    assert result.dtype == dummy_frame.dtype

def test_capture_crop_out_of_bounds(dummy_command):
    cmd, hardware_facade, _, _, _ = dummy_command
    import numpy as np
    dummy_frame = np.ones((720, 1280, 3), dtype=np.uint8)
    hardware_facade._frame = dummy_frame
    with pytest.raises(ValueError):
        cmd.capture(crop_region=(1200, 700, 200, 200))
