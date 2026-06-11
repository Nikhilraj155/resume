import logging
import os
import sys

# Get log level from environment or default to INFO
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# Define formatter
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
formatter = logging.Formatter(LOG_FORMAT)

# Setup standard output handler
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)

# Setup root logger configuration
root_logger = logging.getLogger()
root_logger.setLevel(LOG_LEVEL)

# Avoid duplicate handlers if logger is re-initialized
if not root_logger.handlers:
    root_logger.addHandler(stdout_handler)

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance for a given module name.
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    return logger
