from nyxpy.framework.core.api.notification_handler import NotificationHandler

class MockNotifier:
    def __init__(self):
        self.calls = []
        self.raise_exc = False
    def notify(self, text, img=None):
        if self.raise_exc:
            raise RuntimeError("fail")
        self.calls.append((text, img))

def test_notification_handler_publish_all():
    n1 = MockNotifier()
    n2 = MockNotifier()
    handler = NotificationHandler([n1, n2])
    handler.publish("msg", img="imgdata")
    assert n1.calls == [("msg", "imgdata")]
    assert n2.calls == [("msg", "imgdata")]

def test_notification_handler_continue_on_exception():
    n1 = MockNotifier(); n1.raise_exc = True
    n2 = MockNotifier()
    handler = NotificationHandler([n1, n2])
    handler.publish("msg")
    assert n2.calls == [("msg", None)]
