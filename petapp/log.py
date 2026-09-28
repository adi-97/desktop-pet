import os
from datetime import datetime

from . import config


def log_error(message):
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        if config.LOG_FILE.exists() and config.LOG_FILE.stat().st_size > config.MAX_LOG_BYTES:
            os.replace(config.LOG_FILE, config.LOG_FILE.with_suffix(".log.1"))
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {str(message)[:4000]}\n")
    except OSError:
        pass
