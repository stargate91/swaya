import os
import sys
import logging
from logging.handlers import RotatingFileHandler


def get_log_filepath() -> str:
    """
    Get the path for the log file.
    Resolves to %APPDATA%/Swaya/logs/swaya.log on Windows,
    or a fallback workspace directory logs/swaya.log if not writable or on other platforms.
    """
    log_dir = None
    
    # Try APPDATA on Windows
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            log_dir = os.path.join(appdata, "Swaya", "logs")
            
    # Fallback to user home directory or local project dir
    if not log_dir:
        home = os.path.expanduser("~")
        log_dir = os.path.join(home, ".swaya", "logs")
        
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "swaya.log")
        # Test if writable
        with open(log_file, "a") as f:
            pass
        return log_file
    except Exception:
        # Final fallback to workspace logs directory
        workspace_log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))
        os.makedirs(workspace_log_dir, exist_ok=True)
        return os.path.join(workspace_log_dir, "swaya.log")


def setup_logger(name: str = "swaya") -> logging.Logger:
    """
    Sets up a logger with a RotatingFileHandler (max 3 files, 5MB each)
    and a StreamHandler for console output.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if setup_logger is called multiple times
    if logger.hasHandlers():
        return logger

    # Log Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Rotating File Handler
    try:
        log_file = get_log_filepath()
        # 5MB = 5 * 1024 * 1024 bytes
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5242880,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not configure file logging: {e}")

    return logger
