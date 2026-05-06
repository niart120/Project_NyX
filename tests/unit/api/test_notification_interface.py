import io

import cv2
import numpy as np
import requests

from nyxpy.framework.core.api.discord_notification import DiscordNotification


def test_discord_notification_notify_text_only(monkeypatch):
    called = {}

    def fake_post(url, data=None, files=None, timeout=None):
        called["url"] = url
        called["data"] = data
        called["files"] = files
        called["timeout"] = timeout

        class Resp:
            pass

        return Resp()

    monkeypatch.setattr(requests, "post", fake_post)

    notifier = DiscordNotification("https://discord/webhook")
    notifier.notify("hello")
    assert called["url"] == "https://discord/webhook"
    assert called["data"] == {"content": "hello"}
    assert called["files"] is None
    assert called["timeout"] == 5


def test_discord_notification_notify_with_image(monkeypatch):
    called = {}

    def fake_post(url, data=None, files=None, timeout=None):
        called["url"] = url
        called["data"] = data
        called["files"] = files
        called["timeout"] = timeout

        class Resp:
            pass

        return Resp()

    monkeypatch.setattr(requests, "post", fake_post)

    def fake_imencode(ext, img):
        return True, np.frombuffer(b"dummy_png_bytes", dtype=np.uint8)

    monkeypatch.setattr(cv2, "imencode", fake_imencode)

    notifier = DiscordNotification("https://discord/webhook")
    notifier.notify("imgmsg", img="dummyimg")
    assert called["data"] == {"content": "imgmsg"}
    assert "file" in called["files"]
    filename, fileobj, mimetype = called["files"]["file"]
    assert filename == "image.png"
    assert isinstance(fileobj, io.BytesIO)
    assert fileobj.getvalue() == b"dummy_png_bytes"
    assert mimetype == "image/png"
    assert called["timeout"] == 5


def test_discord_notification_notify_error(monkeypatch):
    logs = []

    class Logger:
        def technical(
            self, level, message, *, component, event="log.message", extra=None, exc=None
        ):
            logs.append((level, message, component, event, exc))

    def fake_imencode(ext, img):
        return False, None

    monkeypatch.setattr(cv2, "imencode", fake_imencode)
    notifier = DiscordNotification("https://discord/webhook", logger=Logger())
    notifier.notify("fail", img="dummyimg")
    assert any(event == "notification.failed" for _, _, _, event, _ in logs)
