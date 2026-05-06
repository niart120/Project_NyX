def check_interrupt(method):
    """
    Command の各操作メソッド実行前に、InterruptController の状態をチェックするデコレータ。
    中断要求があれば MacroCancelled を発生させる。
    """

    def wrapper(self, *args, **kwargs):
        if self.ct:
            self.ct.throw_if_requested()
        return method(self, *args, **kwargs)

    return wrapper
