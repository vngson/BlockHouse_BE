import logging
import os
import re
import copy
from datetime import datetime
from typing import Optional, Dict, List

class ANSIColorFormatter(logging.Formatter):
    """Custom formatter that adds ANSI color codes to log messages for terminal output."""
    
    COLORS: Dict[str, str] = {
        'DEBUG': '\033[36m',       # Cyan
        'INFO': '\033[32m',        # Green
        'WARNING': '\033[33;1m',   # Bright Yellow
        'ERROR': '\033[31;1m',     # Bright Red
        'CRITICAL': '\033[41;97m'  # White on Red background
    }
    RESET: str = '\033[0m'
    LOGGER_NAME_COLOR: str = '\033[35m'  # Purple for logger names

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors for terminal output."""
        record = copy.copy(record)
        
        level_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{level_color}{record.levelname}{self.RESET}"
        record.name = f"{self.LOGGER_NAME_COLOR}{record.name}{self.RESET}"
        
        return super().format(record)

class ANSIStrippingFilter(logging.Filter):
    """Filter to remove ANSI color codes from log messages."""
    
    ANSI_ESCAPE_REGEX = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def filter(self, record: logging.LogRecord) -> bool:
        """Remove ANSI escape sequences from the log message."""
        if record.msg:
            record.msg = self.ANSI_ESCAPE_REGEX.sub('', str(record.msg))
        if record.args and isinstance(record.args, dict):
            record.args = {k: self.ANSI_ESCAPE_REGEX.sub('', str(v)) 
                          for k, v in record.args.items()}
        return True

class LoggerFactory:
    """Factory class for creating and configuring loggers."""
    
    DEFAULT_LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    DEFAULT_LOG_DIR = 'logs'
    
    @classmethod
    def create_logger(
        cls,
        name: str = 'app_logger',
        level: int = logging.INFO,
        log_dir: Optional[str] = None,
        log_format: Optional[str] = None,
        propagate: bool = False
    ) -> logging.Logger:
        """Create and configure a logger with both file and console handlers."""
        log_dir = log_dir or cls.DEFAULT_LOG_DIR
        log_format = log_format or cls.DEFAULT_LOG_FORMAT
        
        logger = logging.getLogger(name)
        
        if not logger.handlers:
            logger.setLevel(level)
            logger.propagate = propagate
            os.makedirs(log_dir, exist_ok=True)
            
            file_handler = cls._create_file_handler(log_dir, log_format)
            console_handler = cls._create_console_handler(log_format)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        
        return logger
    
    @classmethod
    def _create_file_handler(cls, log_dir: str, log_format: str) -> logging.FileHandler:
        """Create a file handler with ANSI stripping."""
        log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
        handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        handler.setFormatter(logging.Formatter(log_format))
        handler.addFilter(ANSIStrippingFilter())
        return handler
    
    @classmethod
    def _create_console_handler(cls, log_format: str) -> logging.StreamHandler:
        """Create a colored console handler."""
        handler = logging.StreamHandler()
        handler.setFormatter(ANSIColorFormatter(log_format))
        return handler

def configure_werkzeug_logger() -> None:
    """Configure werkzeug logger to use our handlers with ANSI stripping."""
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.handlers.clear()  # Remove existing handlers
    
    # Create new handlers with ANSI stripping for file
    log_dir = LoggerFactory.DEFAULT_LOG_DIR
    log_format = LoggerFactory.DEFAULT_LOG_FORMAT
    
    # File handler with ANSI stripping
    file_handler = LoggerFactory._create_file_handler(log_dir, log_format)
    
    # Console handler with colors (optional)
    console_handler = LoggerFactory._create_console_handler(log_format)
    
    werkzeug_logger.addHandler(file_handler)
    werkzeug_logger.addHandler(console_handler)
    werkzeug_logger.propagate = False

# Initialize the global logger
logger = LoggerFactory.create_logger()
configure_werkzeug_logger()