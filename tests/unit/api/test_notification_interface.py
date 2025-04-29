import requests
from nyxpy.framework.core.api.discord_notification import DiscordNotification
from nyxpy.framework.core.api.bluesky_notification import BlueskyNotification

def test_discord_notification_notify(monkeypatch):
    called = {}
    def fake_post(url, data=None, files=None, timeout=None):
        called['url'] = url; called['data'] = data; called['files'] = files; called['timeout'] = timeout
        class Resp: pass
        return Resp()
    monkeypatch.setattr(requests, "post", fake_post)
    notifier = DiscordNotification("https://discord/webhook")
    # テキストのみ
    notifier.notify("hello")
    assert called['url'] == "https://discord/webhook"
    assert called['data'] == {'content': 'hello'}
    assert called['files'] is None
    # 画像付き（cv2.imwriteもモック）
    import cv2
    monkeypatch.setattr(cv2, "imwrite", lambda path, img: True)
    class DummyFile:
        def __init__(self):
            self.contents = b""
            self.closed = False
            self.name = "dummy"
            self.mode = "w+b"
            self.pos = 0
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): self.close()
        def read(self, *a, **k): return self.contents
        def write(self, data): self.contents += data; return len(data)
        def close(self): self.closed = True
        def flush(self): pass
        def seek(self, offset, whence=0): self.pos = offset
        def tell(self): return self.pos
        def readline(self, *a, **k): return b""
        def readlines(self, *a, **k): return []
        def writable(self): return True
        def readable(self): return True
        def seekable(self): return True
        def truncate(self, size=None): pass
    monkeypatch.setattr("builtins.open", lambda path, mode: DummyFile())
    monkeypatch.setattr("os.remove", lambda path: None)
    notifier.notify("imgmsg", img="dummyimg")
    assert called['files'] is not None

def test_bluesky_notification_notify(monkeypatch):
    called = {}
    def fake_post(url, json=None, timeout=None):
        called['url'] = url; called['json'] = json; called['timeout'] = timeout
        class Resp: pass
        return Resp()
    monkeypatch.setattr(requests, "post", fake_post)
    notifier = BlueskyNotification("https://bluesky/webhook")
    notifier.notify("hi")
    assert called['url'] == "https://bluesky/webhook"
    assert called['json'] == {'text': 'hi'}
