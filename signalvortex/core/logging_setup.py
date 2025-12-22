"""Structured logging configuration."""

import logging
import sys
from pathlib import Path
from typing import Optional

def setup_logging(
    log_level: int = logging.INFO,
    log_file: Optional[Path] = None,
    json_format: bool = False
) -> None:
    """Configure logging for the application.
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Path to log file (optional)
        json_format: Whether to use JSON formatting (not implemented yet, placeholder)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatters
    verbose_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(verbose_formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler
    if log_file:
        # Ensure directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(verbose_formatter)
        root_logger.addHandler(file_handler)
        
    # Silence noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
