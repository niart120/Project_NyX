from loguru import logger
import sys
from typing import Callable, Any

class LogManager:
    def __init__(self):
        # Remove any default loguru handlers
        logger.remove()
        # Console handler: For user notifications and debugging (all levels)
        logger.add(sys.stdout, level="DEBUG", colorize=True)
        # File handler: For debug, framework and error logs (rotating file)
        logger.add("logs/logfile.log", level="DEBUG", rotation="1 MB")
    
    def log(self, level: str, message: str, component: str = "") -> None:
        formatted = f"[{component}] {message}" if component else message
        logger.log(level.upper(), formatted)
    
    def set_level(self, level: str) -> None:
        # Remove and add new handlers with the new level
        logger.remove()
        logger.add(sys.stdout, level=level.upper(), colorize=True)
        logger.add("logs/logfile.log", level=level.upper(), rotation="1 MB")
    
    def add_handler(self, handler: Callable[..., Any]) -> None:
        # Allow adding custom handlers (must be a loguru-compatible call)
        logger.add(handler)

# Create a global instance for use across the framework
log_manager = LogManager()
