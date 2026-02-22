"""
テキストの視覚属性推定と共通データ形式（Req: 3.4）

OCR 結果にフォントサイズ・色・太さを推定して付与し、PPTX 出力用の共通データ形式に整備する。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .models import TextElement


# ピクセル高さ → ポイントの概算（96 DPI 想定: 1 pt ≈ 1.33 px）
PX_TO_PT_RATIO = 72.0 / 96.0


def _crop_bbox(image: Image.Image, bbox: tuple[float, float, float, float]) -> Image.Image:
    """画像から bbox (x_min, y_min, x_max, y_max) 領域をクロップする。"""
    x_min, y_min, x_max, y_max = bbox
    x_min, x_max = max(0, int(x_min)), min(image.width, int(x_max))
    y_min, y_max = max(0, int(y_min)), min(image.height, int(y_max))
    if x_max <= x_min or y_max <= y_min:
        return image.crop((0, 0, 1, 1))
    return image.crop((x_min, y_min, x_max, y_max))


def _estimate_font_size_pt(bbox: tuple[float, float, float, float]) -> float | None:
    """bbox の高さからフォントサイズ（pt）を概算する。"""
    _, y_min, _, y_max = bbox
    h = y_max - y_min
    if h <= 0:
        return None
    return round(h * PX_TO_PT_RATIO, 1)


def _estimate_font_color(crop: Image.Image) -> str | None:
    """クロップ領域の代表色を #RRGGBB で返す。RGB モードに変換して中央付近のピクセル中央値を使用。"""
    if crop.size[0] * crop.size[1] == 0:
        return None
    rgb = crop.convert("RGB")
    pixels = list(rgb.getdata())
    if not pixels:
        return None
    r = sorted(p[0] for p in pixels)[len(pixels) // 2]
    g = sorted(p[1] for p in pixels)[len(pixels) // 2]
    b = sorted(p[2] for p in pixels)[len(pixels) // 2]
    return f"#{r:02x}{g:02x}{b:02x}"


def _estimate_is_bold(_crop: Image.Image) -> bool | None:
    """簡易ヒューリスティック: テキスト領域のコントラストが高いと太字の可能性。ここでは未実装のため None。"""
    return None


def estimate_visual_attributes(
    elements: list[TextElement],
    image_path: str | Path,
) -> list[TextElement]:
    """
    OCR で得た TextElement リストに、画像から推定したフォントサイズ・色を付与する。
    bbox はピクセル座標であること。返却もピクセル座標のまま（共通データ形式で統一）。

    Args:
        elements: PaddleOCR 等の結果（bbox はピクセル）
        image_path: 元画像パス（クロップ用）

    Returns:
        font_size_pt, font_color を推定で埋めた TextElement のリスト。is_bold は None のまま。
    """
    path = Path(image_path)
    if not path.exists():
        return elements

    image = Image.open(path).convert("RGB")
    result: list[TextElement] = []
    for el in elements:
        bbox = el.get("bbox")
        if not bbox or len(bbox) != 4:
            result.append(el)
            continue
        crop = _crop_bbox(image, bbox)
        font_size_pt = _estimate_font_size_pt(bbox)
        font_color = _estimate_font_color(crop)
        is_bold = _estimate_is_bold(crop)
        result.append(
            TextElement(
                text=el.get("text", ""),
                bbox=bbox,
                confidence=el.get("confidence", 0.0),
                font_size_pt=font_size_pt,
                font_color=font_color,
                is_bold=is_bold,
            )
        )
    return result


def normalize_bbox_to_01(
    elements: list[TextElement],
    image_width: int,
    image_height: int,
) -> list[TextElement]:
    """
    ピクセル座標の bbox を 0–1 正規化する。
    PPTX 側でスライド寸法に合わせてスケールする際に利用可能。
    """
    if image_width <= 0 or image_height <= 0:
        return elements
    result: list[TextElement] = []
    for el in elements:
        bbox = el.get("bbox")
        if not bbox or len(bbox) != 4:
            result.append(el)
            continue
        x_min, y_min, x_max, y_max = bbox
        nbox = (
            x_min / image_width,
            y_min / image_height,
            x_max / image_width,
            y_max / image_height,
        )
        result.append(
            TextElement(
                text=el.get("text", ""),
                bbox=nbox,
                confidence=el.get("confidence", 0.0),
                font_size_pt=el.get("font_size_pt"),
                font_color=el.get("font_color"),
                is_bold=el.get("is_bold"),
            )
        )
    return result
