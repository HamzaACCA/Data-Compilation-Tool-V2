"""
Logging utility for Data Compilation Tool
Provides colored console output and rotating file logs.

Usage:
    from utils.logging import setup_logging, get_logger

    # Call once at startup (pass APP_DIR so logs land next to data)
    setup_logging(log_dir)

    # In any module
    log = get_logger(__name__)
    log.info("Server started on port %d", port)
    log.warning("Cache miss for project %s", project_name)
    log.error("Upload failed: %s", str(e))
"""

import logging
import logging.handlers
import os
import sys

# ---------------------------------------------------------------------------
# ANSI color codes (works in most terminals; stripped on Windows if needed)
# ---------------------------------------------------------------------------
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_COLORS = {
    "DEBUG":    "\033[36m",   # Cyan
    "INFO":     "\033[32m",   # Green
    "WARNING":  "\033[33m",   # Yellow
    "ERROR":    "\033[31m",   # Red
    "CRITICAL": "\033[35m",   # Magenta
}

_ANSI_ENABLED = sys.stdout.isatty() or os.environ.get("FORCE_COLOR")


class _ColorFormatter(logging.Formatter):
    """Formatter that prepends a color-coded level tag to each line."""

    FMT = "{color}{bold}[{level:<8}]{reset} {dim}{name}{reset}  {msg}"

    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelname, "")
        bold  = _BOLD if record.levelno >= logging.WARNING else ""
        dim   = "\033[2m"   # Dim for logger name

        # Build the prefix
        if _ANSI_ENABLED:
            prefix = (
                f"{color}{bold}[{record.levelname:<8}]{_RESET} "
                f"{dim}{record.name}{_RESET}  "
            )
        else:
            prefix = f"[{record.levelname:<8}] {record.name}  "

        # Timestamp
        ts = self.formatTime(record, "%H:%M:%S")

        # Exception info (appended after message)
        record.message = record.getMessage()
        exc_text = ""
        if record.exc_info:
            exc_text = "\n" + self.formatException(record.exc_info)

        return f"{ts}  {prefix}{record.message}{exc_text}"


class _PlainFormatter(logging.Formatter):
    """Plain formatter for log files (no ANSI codes)."""

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        exc_text = ""
        if record.exc_info:
            exc_text = "\n" + self.formatException(record.exc_info)
        return f"{ts}  [{record.levelname:<8}] {record.name}  {record.getMessage()}{exc_text}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logging(
    log_dir: str,
    *,
    console_level: int = logging.INFO,
    file_level: int    = logging.DEBUG,
    max_bytes: int     = 2 * 1024 * 1024,   # 2 MB per file
    backup_count: int  = 3,
    log_filename: str  = "app.log",
) -> None:
    """
    Configure the root logger.  Call this once at application startup.

    Args:
        log_dir:       Directory where the rotating log file will be written.
        console_level: Minimum level printed to stdout (default: INFO).
        file_level:    Minimum level written to the log file (default: DEBUG).
        max_bytes:     Max size per log file before rotation (default: 2 MB).
        backup_count:  Number of rotated files to keep (default: 3).
        log_filename:  Name of the log file (default: app.log).
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_filename)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)          # let handlers filter

    # Avoid adding duplicate handlers if setup_logging is called again
    if root.handlers:
        root.handlers.clear()

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(_ColorFormatter())
    root.addHandler(console_handler)

    # --- Rotating file handler ---
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(_PlainFormatter())
    root.addHandler(file_handler)

    # Silence noisy third-party loggers
    for noisy in ("werkzeug", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.  Use __name__ as the name for easy tracing.

    Example:
        log = get_logger(__name__)
        log.info("Project created: %s", project_name)
    """
    return logging.getLogger(name)
