"""
処理のボトルネック特定用デバッグログ。
環境変数 KIRIGAMI_DEBUG=1 のときだけ temp にタイムスタンプ付きログを書く。
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

_enabled = os.environ.get("KIRIGAMI_DEBUG", "").strip() in ("1", "true", "yes")
_lock = threading.Lock()
_start = time.monotonic()


def _log_path() -> Path:
    base = Path(__file__).resolve().parent.parent
    return base / "temp" / "kirigami_debug.log"


def log(msg: str) -> None:
    if not _enabled:
        return
    elapsed = time.monotonic() - _start
    tid = threading.current_thread().name
    line = f"[{elapsed:.1f}s] [{tid}] {msg}\n"
    with _lock:
        p = _log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)
