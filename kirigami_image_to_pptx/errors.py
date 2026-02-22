"""
エラー処理とユーザー向けメッセージ（Req: 8.4）

入力エラー・API エラー時の明確な報告と代替手段の案内。
"""
from __future__ import annotations

from pathlib import Path

# 進捗・エラー文言の一貫表示用（CLI / Web UI で共通）
PROGRESS_PREPROCESS = "前処理・正規化"
PROGRESS_DECOMPOSE = "レイヤー分解"
PROGRESS_OCR = "テキスト抽出"
PROGRESS_LLM = "LLM 補正"
PROGRESS_PPTX = "PPTX 生成"
PROGRESS_DONE = "完了"

# 入力エラー
MSG_FILE_NOT_FOUND = "ファイルが見つかりません: {path}"
MSG_UNSUPPORTED_IMAGE = "対応していない画像形式です: {suffix}。対応形式: PNG, JPEG, WebP"
MSG_UNSUPPORTED_INPUT = "対応していない入力です。画像（PNG/JPEG/WebP）または PDF を指定してください。"

# API エラーと代替案内
MSG_FAL_KEY_MISSING = "FAL_KEY が設定されていません。.env に設定するか、--backend cpu でローカル分解を試してください。"
MSG_GOOGLE_KEY_MISSING = "GOOGLE_API_KEY（または GEMINI_API_KEY）が設定されていません。Vision OCR を使う場合は .env に設定してください。"
MSG_LLM_UNAVAILABLE = "LLM 補正に必要な API キーがありません。--no-llm-correct で補正を無効にできます。"


def validate_input_path(path: str | Path) -> None:
    """
    入力パスが存在し対応形式であることを検証する。
    対応形式でない・ファイル不存在の場合は明確な例外を発生させる。
    """
    from .image_utils import SUPPORTED_EXTENSIONS

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(MSG_FILE_NOT_FOUND.format(path=p))
    if p.is_dir():
        return
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(MSG_UNSUPPORTED_IMAGE.format(suffix=suffix))
