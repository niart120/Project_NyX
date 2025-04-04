import inspect

def get_caller_class_name():
    """呼び出し元のクラス名を取得する関数"""
    frame = inspect.currentframe().f_back  # 呼び出し元のフレーム
    self_var = frame.f_locals.get("self")  # 呼び出し元のローカル変数 `self`
    return type(self_var).__name__ if self_var else None