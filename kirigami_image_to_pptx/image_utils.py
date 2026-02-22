"""
画像の読み込みと正規化（Req: 1.1, 1.6）

PNG / JPEG / WebP の読み込みと後段が扱いやすい形式への正規化。
解像度のリサイズとレイヤー分解・OCR 入力としての形式の保証。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

# 対応形式（読み込み用）
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _open_with_pillow(path: str | Path) -> Image.Image:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format: {suffix}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    img = Image.open(path)
    return img.convert("RGBA" if img.mode in ("P", "RGBA") else "RGB")


def load_image(path: str | Path) -> Image.Image:
    """
    画像ファイルを読み込み、PIL Image で返す。
    対応形式: PNG, JPEG, WebP。RGBA または RGB に正規化する。
    """
    return _open_with_pillow(path)


def normalize_image(
    image: Image.Image,
    max_size: int = 640,
) -> Image.Image:
    """
    解像度を max_size 以下にリサイズし、後段（decompose / OCR）が扱いやすい形式にする。
    アスペクト比は維持する。既に max_size 以下ならそのまま返す。
    """
    w, h = image.size
    if w <= max_size and h <= max_size:
        return image
    if w >= h:
        new_w = max_size
        new_h = int(h * max_size / w)
    else:
        new_h = max_size
        new_w = int(w * max_size / h)
    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)


def load_and_normalize(
    path: str | Path,
    max_size: int = 640,
) -> Image.Image:
    """load_image と normalize_image をまとめて実行する。"""
    img = load_image(path)
    return normalize_image(img, max_size=max_size)
