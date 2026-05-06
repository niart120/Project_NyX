class ConfigurationError(ValueError):
    """設定の解決・検証に失敗したことを表す例外。"""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code
