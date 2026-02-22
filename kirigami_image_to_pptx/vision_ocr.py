"""
Vision API による一括テキスト抽出（Req: 3.5）

画像を Gemini Vision API に渡し、テキスト・座標・属性を一括で取得する代替ルート。
"""
from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

from .models import TextElement

logger = logging.getLogger(__name__)

_VISION_PROMPT = """Analyze this image and list every text region as a JSON array.
Return ONLY a valid JSON array, no other text. Each item must have:
- "text": the exact text string
- "bbox": [x_min, y_min, x_max, y_max] in normalized coordinates (0.0 to 1.0), relative to image width and height
- "confidence": number between 0 and 1 (optional, use 0.95 if unsure)
- "font_size_pt": approximate font size in points (optional, null if unknown)
- "font_color": hex color like "#RRGGBB" (optional, null if unknown)
- "is_bold": true/false (optional, null if unknown)

Example: [{"text": "Hello", "bbox": [0.1, 0.2, 0.5, 0.25], "confidence": 0.98}]
"""


def _load_image_base64(image_path: str | Path) -> tuple[str, str, int, int]:
    """画像を読み込み、base64 と MIME と幅・高さを返す。"""
    from PIL import Image

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    img = Image.open(path)
    img = img.convert("RGB")
    w, h = img.size
    buf = __import__("io").BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/png"
    return b64, mime, w, h


def _parse_vision_response(response_text: str, image_width: int, image_height: int) -> list[TextElement]:
    """Vision API の応答テキストをパースして TextElement のリストにする。"""
    text = (response_text or "").strip()
    # JSON 配列を抽出（マークダウンコードブロックを除去）
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        logger.warning("Vision API response contained no JSON array: %s", text[:200])
        return []

    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse Vision JSON: %s", e)
        return []

    elements: list[TextElement] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        t = item.get("text") or ""
        bbox_raw = item.get("bbox")
        if not bbox_raw or len(bbox_raw) != 4:
            continue
        # 正規化 0-1 ならそのまま、またはピクセルに変換
        x_min, y_min, x_max, y_max = [float(x) for x in bbox_raw]
        if all(0 <= v <= 1.01 for v in (x_min, y_min, x_max, y_max)):
            # 正規化座標をピクセルに変換（後段で共通化しやすいようピクセルで統一してもよい）
            bbox = (
                x_min * image_width,
                y_min * image_height,
                x_max * image_width,
                y_max * image_height,
            )
        else:
            bbox = (x_min, y_min, x_max, y_max)
        conf = item.get("confidence")
        if conf is None:
            conf = 0.95
        conf = max(0.0, min(1.0, float(conf)))
        font_pt = item.get("font_size_pt")
        if font_pt is not None:
            font_pt = float(font_pt)
        font_color = item.get("font_color")
        if font_color is not None:
            font_color = str(font_color).strip() or None
        is_bold = item.get("is_bold")
        if is_bold is not None and not isinstance(is_bold, bool):
            is_bold = None
        elements.append(
            TextElement(
                text=t,
                bbox=bbox,
                confidence=conf,
                font_size_pt=font_pt,
                font_color=font_color,
                is_bold=is_bold,
            )
        )
    return elements


# 既定の Vision モデル（config 未指定時）
DEFAULT_VISION_MODEL = "gemini-3-pro-preview"


def extract_text_with_vision(
    image_path: str | Path,
    get_env: callable | None = None,
    model_id: str | None = None,
) -> list[TextElement]:
    """
    画像を Vision API に渡し、テキスト・座標・属性を一括で取得する。

    Args:
        image_path: 画像ファイルパス
        get_env: 環境変数取得関数（GOOGLE_API_KEY 用）。None の場合は os.environ.get
        model_id: Gemini モデル ID。None の場合は gemini-3-pro-preview（config から渡す場合は config.models.gemini）

    Returns:
        TextElement のリスト（bbox はピクセル座標）
    """
    import os

    get_env = get_env or (lambda k, default="": os.environ.get(k, default))
    api_key = get_env("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set. Set it in .env or environment for Vision OCR.")

    b64, mime, width, height = _load_image_base64(image_path)

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_id or DEFAULT_VISION_MODEL)
    contents = [
        {"inline_data": {"mime_type": mime, "data": b64}},
        _VISION_PROMPT,
    ]
    response = model.generate_content(contents)
    response_text = getattr(response, "text", None)
    if not response_text and response.candidates and response.candidates[0].content.parts:
        response_text = response.candidates[0].content.parts[0].text
    return _parse_vision_response(response_text or "", width, height)
