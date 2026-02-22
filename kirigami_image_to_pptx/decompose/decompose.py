"""
レイヤー分解オーケストラ（Req: 2.1–2.6）

- backend "api": fal.ai を呼び出し、返却 URL から画像をダウンロードして temp に保存。
- backend "cpu": ローカル推論（diffusers）。CUDA は使用しない。オプション依存。
"""
from __future__ import annotations

import logging
import urllib.request
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

MODEL_ID = "fal-ai/qwen-image-layered"


def _decompose_api(
    image_path: str | Path,
    num_layers: int,
    output_dir: str | Path,
    get_env: callable,  # (key: str, default: str = "") -> str
) -> list[str]:
    """fal.ai API でレイヤー分解し、output_dir に PNG を保存してパスリストを返す。"""
    try:
        import fal_client
    except ImportError:
        raise ImportError("fal-client is required for backend='api'. Install with: pip install fal-client") from None

    key = get_env("FAL_KEY")
    if not key:
        raise ValueError("FAL_KEY is not set. Set it in .env or environment.")

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    # ローカルファイルを fal に渡す（data URI または upload）
    try:
        image_url = fal_client.encode_file(str(path))
    except Exception as e:
        logger.debug("encode_file failed, trying upload_file: %s", e)
        image_url = fal_client.upload_file(str(path))

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    result = fal_client.subscribe(
        MODEL_ID,
        arguments={
            "image_url": image_url,
            "num_layers": max(1, min(10, num_layers)),
            "output_format": "png",
        },
    )

    images = result.get("images") or []
    paths: list[str] = []
    for i, img in enumerate(images):
        url = img.get("url") if isinstance(img, dict) else getattr(img, "url", None)
        if not url:
            continue
        dest = out / f"layer_{i:02d}.png"
        urllib.request.urlretrieve(url, dest)
        paths.append(str(dest))

    return paths


def _decompose_cpu(
    image_path: str | Path,
    num_layers: int,
    output_dir: str | Path,
) -> list[str]:
    """
    CPU 推論でレイヤー分解（CUDA 非使用）。
    diffusers の QwenImageLayeredPipeline が利用可能な場合はそれを使用し、
    そうでない場合は入力画像を 1 枚のレイヤーとして返す（オフライン動作のフォールバック）。
    """
    from PIL import Image

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    image = Image.open(path).convert("RGBA")

    layers: list = []
    try:
        import torch
        from diffusers import QwenImageLayeredPipeline
        pipe = QwenImageLayeredPipeline.from_pretrained("Qwen/Qwen-Image-Layered")
        pipe = pipe.to("cpu")
        result = pipe(image, num_layers=num_layers)
        layers = getattr(result, "images", result) if hasattr(result, "images") else [image]
    except ImportError:
        logger.info(
            "CPU decompose: torch/diffusers not installed. Using single-layer fallback. "
            "For full CPU decomposition, install: torch diffusers transformers"
        )
        layers = [image]
    except Exception as e:
        logger.warning("CPU decompose pipeline failed (%s). Using single-layer fallback.", e)
        layers = [image]

    paths = []
    for i, layer_img in enumerate(layers[:num_layers]):
        dest = out / f"layer_{i:02d}.png"
        if hasattr(layer_img, "save"):
            layer_img.save(dest)
        else:
            Image.fromarray(layer_img).save(dest)
        paths.append(str(dest))

    return paths


def decompose_image(
    image_path: str | Path,
    num_layers: int = 4,
    backend: Literal["api", "cpu"] = "api",
    output_dir: str | Path | None = None,
    get_env: callable | None = None,
) -> list[str]:
    """
    画像を複数 RGBA レイヤーに分解し、レイヤー画像のファイルパスリスト（Z-order 順）を返す。

    Args:
        image_path: 入力画像パス
        num_layers: レイヤー数（3–10）
        backend: "api"（fal.ai）または "cpu"（ローカル推論）
        output_dir: 保存先。None の場合は一時ディレクトリを使用
        get_env: 環境変数取得関数（backend="api" で FAL_KEY 用）。None の場合は os.environ.get

    Returns:
        レイヤー画像のファイルパスリスト（先頭が背景、末尾が前面）
    """
    import os
    num_layers = max(3, min(10, num_layers))
    if output_dir is None:
        import tempfile
        output_dir = tempfile.mkdtemp(prefix="kirigami_decompose_")
    get_env = get_env or (lambda k, default="": os.environ.get(k, default))

    if backend == "api":
        return _decompose_api(image_path, num_layers, output_dir, get_env)
    if backend == "cpu":
        return _decompose_cpu(image_path, num_layers, output_dir)
    raise ValueError(f"Unknown backend: {backend}. Use 'api' or 'cpu'.")
