"""
パイプライン共通のデータ型（Req: 3.1–3.4, 5.1）

OCR・補正・PPTX 間で共有する TextElement 等を定義する。
"""
from __future__ import annotations

from typing import TypedDict


class TextElement(TypedDict, total=False):
    """テキスト要素の共通型。OCR と LLM 補正・PPTX 出力で共有する。"""
    text: str
    bbox: tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max) ピクセルまたは 0–1 正規化
    confidence: float
    font_size_pt: float | None
    font_color: str | None  # #RRGGBB
    is_bold: bool | None
