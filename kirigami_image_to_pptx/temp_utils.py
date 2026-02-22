"""
中間ファイルの一時ディレクトリ出力と処理後の削除オプション（Req: 7.4）

clean_temp が True のとき、指定パスを削除する。削除失敗はログのみで処理は成功とする。
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config_loader import AppConfig

logger = logging.getLogger(__name__)


def cleanup_temp_files(
    paths: list[str | Path],
    *,
    clean: bool = True,
) -> None:
    """
    一時ファイル・ディレクトリを削除する。clean が False のときは何もしない。
    削除に失敗した場合はログに記録するだけで例外は出さない。
    """
    if not clean or not paths:
        return
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=False)
        except OSError as e:
            logger.warning("Failed to remove temp path %s: %s", path, e)
