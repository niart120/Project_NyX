from nyxpy.framework.core.macro.exceptions import MacroStopException

def check_interrupt(method):
    """
    Command の各操作メソッド実行前に、InterruptController の状態をチェックするデコレータ。
    中断要求があれば MacroStopException を発生させる。
    """
    def wrapper(self, *args, **kwargs):
        if self.ct and self.ct.stop_requested():
            raise MacroStopException("Macro execution interrupted.")
        return method(self, *args, **kwargs)
    return wrapper
