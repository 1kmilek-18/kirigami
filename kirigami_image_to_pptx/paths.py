"""
入出力・一時用ディレクトリの存在保証（Req: 7.1, 8.2）

設定で指定された入力用・出力用・一時用ディレクトリを用意し、
存在しない場合は作成する。config のパスと対応させる。
"""
from __future__ import annotations

import os
from pathlib import Path


# 設定未指定時のデフォルトディレクトリ名（プロジェクトルート基準）
DEFAULT_INPUT_DIR = "input"
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_TEMP_DIR = "temp"


def ensure_directories(
    input_dir: str | Path,
    output_dir: str | Path,
    temp_dir: str | Path,
    *,
    base_path: str | Path | None = None,
) -> tuple[Path, Path, Path]:
    """
    入力用・出力用・一時用ディレクトリが存在することを保証する。
    相対パスは base_path を基準に解決する（未指定時はカレントディレクトリ）。

    Returns:
        (input_path, output_path, temp_path) の絶対 Path
    """
    base = Path(base_path) if base_path is not None else Path.cwd()
    paths = [
        base / input_dir,
        base / output_dir,
        base / temp_dir,
    ]
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
    return tuple(p.resolve() for p in paths)


def get_default_dirs(base_path: str | Path | None = None) -> tuple[str, str, str]:
    """
    デフォルトの入力・出力・一時ディレクトリ名を返す。
    設定ファイルで上書きされない場合に使用する。
    """
    return (DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_TEMP_DIR)
