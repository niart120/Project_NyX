class MacroStopException(Exception):
    """
    マクロの中断要求が発生した場合に送出される例外。
    この例外をキャッチすることで、マクロ実行を安全に停止することができます。
    """
    pass
