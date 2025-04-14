from loguru import logger
import sys
from typing import Callable, Any

class LogManager:
    def __init__(self):
        # Remove any default loguru handlers
        logger.remove()

        # Built-in handlers (console & file)
        self.console_handler_id = logger.add(sys.stdout, level="DEBUG", colorize=True)
        self.file_handler_id = logger.add("logs/logfile.log", level="DEBUG", rotation="1 MB")

        # Custom handlers storage
        self.custom_handlers: dict[Callable[..., Any], int] = {}

    def log(self, level: str, message: str, component: str = "") -> None:
        formatted = f"[{component}] {message}" if component else message
        logger.log(level.upper(), formatted)

    def set_level(self, level: str) -> None:
        """すべてのログハンドラのログレベルを変更"""
        logger.remove(self.console_handler_id)
        logger.remove(self.file_handler_id)
        self.console_handler_id = logger.add(sys.stdout, level=level.upper(), colorize=True)
        self.file_handler_id = logger.add("logs/logfile.log", level=level.upper(), rotation="1 MB")

        for handler, handler_id in self.custom_handlers.items():
            logger.remove(handler_id)
            new_handler_id = logger.add(handler, level=level.upper())
            self.custom_handlers[handler] = new_handler_id

    def set_console_level(self, level: str) -> None:
        """コンソール出力のログレベルのみを変更"""
        logger.remove(self.console_handler_id)
        self.console_handler_id = logger.add(sys.stdout, level=level.upper(), colorize=True)

    def set_file_level(self, level: str) -> None:
        """ファイル出力のログレベルのみを変更"""
        logger.remove(self.file_handler_id)
        self.file_handler_id = logger.add("logs/logfile.log", level=level.upper(), rotation="1 MB")

    def add_handler(self, handler: Callable[..., Any], level: str = "DEBUG") -> None:
        """カスタムハンドラを追加"""
        if handler in self.custom_handlers:
            raise ValueError("指定されたハンドラは既に登録されています")
        handler_id = logger.add(handler, level=level.upper())
        self.custom_handlers[handler] = handler_id

    def set_custom_handler_level(self, handler: Callable[..., Any], level: str) -> None:
        """指定したカスタムハンドラのログレベルを変更"""
        if handler not in self.custom_handlers:
            raise ValueError("指定されたハンドラは登録されていません")
        handler_id = self.custom_handlers[handler]
        logger.remove(handler_id)
        new_handler_id = logger.add(handler, level=level.upper())
        self.custom_handlers[handler] = new_handler_id

    def remove_handler(self, handler: Callable[..., Any]) -> None:
        """カスタムハンドラを削除"""
        if handler not in self.custom_handlers:
            raise ValueError("指定されたハンドラは登録されていません")
        handler_id = self.custom_handlers.pop(handler)
        logger.remove(handler_id)

# Create a global instance for use across the framework
log_manager = LogManager()
