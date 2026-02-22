"""
ローカル OCR によるテキスト・座標抽出（Req: 3.1, 3.2, 3.3）

画像内テキストの認識とテキスト内容・境界ボックス・信頼度の取得。日本語・英語対応。
フォントサイズ・色・太さは 4.2 で推定するため、ここでは None を返す。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import TextElement


def _box_to_bbox(box: list[list[float]]) -> tuple[float, float, float, float]:
    """PaddleOCR の 4 点 box を (x_min, y_min, x_max, y_max) に変換する。"""
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return (min(xs), min(ys), max(xs), max(ys))


def extract_text(
    image_path: str | Path,
    lang: str = "japan",
) -> list[TextElement]:
    """
    画像からテキスト・bbox・信頼度を抽出する。

    Args:
        image_path: 画像ファイルパス
        lang: 言語（'japan' または 'en'）

    Returns:
        TextElement のリスト（bbox はピクセル座標）
    """
    from paddleocr import PaddleOCR

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    result = ocr.ocr(str(path), cls=True)

    elements: list[TextElement] = []
    if not result:
        return elements

    # result は [ページごとのリスト]。1 画像の場合は result[0]
    page = result[0] if result else []
    for line in page:
        if not line or len(line) < 2:
            continue
        box, text_part = line[0], line[1]
        if isinstance(text_part, (list, tuple)) and len(text_part) >= 2:
            text, confidence = text_part[0], text_part[1]
        else:
            text, confidence = str(text_part), 0.0
        if not isinstance(confidence, (int, float)):
            confidence = float(confidence) if confidence else 0.0
        bbox = _box_to_bbox(box)
        elements.append(
            TextElement(
                text=str(text).strip(),
                bbox=bbox,
                confidence=float(confidence),
                font_size_pt=None,
                font_color=None,
                is_bold=None,
            )
        )

    return elements
