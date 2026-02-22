"""
パイプライン統合（Req: 7.1–7.3）

前処理 → レイヤー分解 → テキスト抽出 → 補正（オプション）→ PPTX 生成の順実行。
config に応じた分解バックエンド・OCR 方式・LLM 補正の有無を反映する。
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from .config_loader import ensure_directories_from_config
from .decompose import decompose_image
from .errors import (
    PROGRESS_DECOMPOSE,
    PROGRESS_DONE,
    PROGRESS_LLM,
    PROGRESS_OCR,
    PROGRESS_PPTX,
    PROGRESS_PREPROCESS,
    validate_input_path,
)
from .fallback import select_llm_provider
from .image_utils import load_and_normalize
from .llm_correct import correct_texts
from .models import TextElement
from .ocr import extract_text
import fitz
from .pdf_utils import pdf_to_images
from .pptx_builder import build_pptx, build_pptx_multi_slides
from .debug_log import log as debug_log
from .temp_utils import cleanup_temp_files
from .text_attributes import estimate_visual_attributes
from .vision_ocr import extract_text_with_vision

if TYPE_CHECKING:
    from .config_loader import AppConfig

logger = logging.getLogger(__name__)


def run_single(
    image_path: str | Path,
    config: AppConfig,
    output_path: str | Path | None = None,
    temp_base: Path | None = None,
) -> str:
    """
    画像 1 枚を前処理 → 分解 → OCR → 補正(オプション) → PPTX 生成まで実行する。

    Returns:
        生成した .pptx のファイルパス
    """
    image_path = Path(image_path)
    validate_input_path(image_path)

    _, output_dir, temp_dir = ensure_directories_from_config(config)
    if temp_base is None:
        temp_base = temp_dir
    run_id = uuid.uuid4().hex[:8]
    work_dir = temp_base / f"run_{run_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    temp_paths: list[Path] = [work_dir]

    try:
        logger.info(PROGRESS_PREPROCESS)
        norm_path = work_dir / "normalized.png"
        img = load_and_normalize(image_path, max_size=config.image.max_resolution)
        img.save(norm_path)
        temp_paths.append(norm_path)

        logger.info(PROGRESS_DECOMPOSE)
        layer_dir = work_dir / "layers"
        layer_dir.mkdir(exist_ok=True)
        layer_paths = decompose_image(
            norm_path,
            num_layers=config.decompose.num_layers,
            backend=config.decompose.backend,
            output_dir=layer_dir,
            get_env=config.get_env,
        )
        temp_paths.extend([Path(p) for p in layer_paths])

        logger.info(PROGRESS_OCR)
        if config.ocr.method == "vision":
            elements = extract_text_with_vision(
                norm_path, get_env=config.get_env, model_id=config.models.gemini
            )
        else:
            elements = extract_text(norm_path, lang=config.ocr.lang)
            elements = estimate_visual_attributes(elements, norm_path)

        if elements and config.llm_correction.enabled:
            logger.info(PROGRESS_LLM)
            provider = select_llm_provider(config)
            if provider:
                try:
                    elements = correct_texts(
                        elements,
                        provider,
                        config.get_env,
                        model_anthropic=config.models.anthropic,
                        model_gemini=config.models.gemini,
                    )
                except Exception as e:
                    logger.warning("LLM correction failed (%s), using uncorrected text.", e)

        logger.info(PROGRESS_PPTX)
        if output_path is None:
            output_path = output_dir / f"{image_path.stem}.pptx"
        output_path = Path(output_path)

        build_pptx(
            layer_paths,
            elements,
            output_path,
            slide_width_inches=config.output.slide_width_inches,
            slide_height_inches=config.output.slide_height_inches,
        )
        logger.info(PROGRESS_DONE)
        return str(output_path)
    finally:
        if config.clean_temp:
            cleanup_temp_files([work_dir], clean=True)


def run_pdf(
    pdf_path: str | Path,
    config: AppConfig,
    output_path: str | Path | None = None,
    temp_base: Path | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> str:
    """
    PDF をページごとに画像化し、各ページを処理して 1 つの .pptx にまとめる（1 入力 1 .pptx）。

    Args:
        progress_callback: (progress_0_to_1, message) で進捗を報告。Web UI 用。

    Returns:
        生成した .pptx のファイルパス
    """
    pdf_path = Path(pdf_path)
    validate_input_path(pdf_path)
    if pdf_path.suffix.lower() != ".pdf":
        from .errors import MSG_UNSUPPORTED_INPUT
        raise ValueError(MSG_UNSUPPORTED_INPUT)

    def report(ratio: float, msg: str) -> None:
        if progress_callback is not None:
            progress_callback(ratio, msg)

    _, output_dir, temp_dir = ensure_directories_from_config(config)
    if temp_base is None:
        temp_base = temp_dir
    run_id = uuid.uuid4().hex[:8]
    work_dir = temp_base / f"pdf_{run_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    debug_log("run_pdf: opening PDF for page count")
    try:
        doc = fitz.open(pdf_path)
        n_pages_total = len(doc)
        doc.close()
        report(0.1, f"PDF を開きました（{n_pages_total} ページ）。画像に変換しています…")
        debug_log(f"run_pdf: PDF has {n_pages_total} pages")
    except Exception as e:
        debug_log(f"run_pdf: open failed {e}")
        n_pages_total = 0

    def pdf_progress(current: int, total: int) -> None:
        # PDF 変換は全体の 0.2 ～ 0.35 の範囲で表示
        if total <= 0:
            report(0.25, "PDF をページ画像に変換…")
        else:
            report(0.2 + 0.15 * (current / total), f"PDF をページ画像に変換… {current}/{total}")

    debug_log("run_pdf: pdf_to_images start")
    page_images = pdf_to_images(
        pdf_path,
        dpi=getattr(config.image, "pdf_dpi", 120),
        temp_dir=work_dir / "pages",
        progress_callback=pdf_progress,
    )
    debug_log(f"run_pdf: pdf_to_images done, {len(page_images)} images")
    temp_paths_to_clean: list[Path] = [work_dir]

    pages_data: list[tuple[list[str], list[TextElement]]] = []
    n_pages = len(page_images)

    try:
        for i, page_path in enumerate(page_images):
            debug_log(f"run_pdf: page {i+1}/{n_pages} start")
            # ページ内で細かく進捗を出して「止まってる」感を減らす（0.35 ～ 0.95 を 1 ページあたり 5 段階で更新）
            def page_progress(sub: float, msg: str) -> None:
                # sub: 0=開始, 0.25=正規化後, 0.5=分解後, 0.75=OCR後, 1.0=LLM後
                r = (i + sub) / n_pages if n_pages else 0
                report(0.35 + 0.6 * r, msg)

            page_progress(0, f"ページ {i + 1}/{n_pages} を処理中…")

            norm_path = work_dir / f"page_{i:04d}_norm.png"
            img = load_and_normalize(page_path, max_size=config.image.max_resolution)
            img.save(norm_path)
            page_progress(0.25, f"ページ {i + 1}/{n_pages} 正規化済み")

            layer_dir = work_dir / f"layers_{i}"
            layer_dir.mkdir(exist_ok=True)
            page_progress(0.3, f"ページ {i + 1}/{n_pages} レイヤー分解中…")
            debug_log(f"run_pdf: page {i+1} decompose start")
            layer_paths = decompose_image(
                norm_path,
                num_layers=config.decompose.num_layers,
                backend=config.decompose.backend,
                output_dir=layer_dir,
                get_env=config.get_env,
            )
            page_progress(0.5, f"ページ {i + 1}/{n_pages} 分解済み")
            debug_log(f"run_pdf: page {i+1} decompose done")

            page_progress(0.55, f"ページ {i + 1}/{n_pages} OCR 中…")
            debug_log(f"run_pdf: page {i+1} OCR start")
            if config.ocr.method == "vision":
                elements = extract_text_with_vision(
                    norm_path, get_env=config.get_env, model_id=config.models.gemini
                )
            else:
                elements = extract_text(norm_path, lang=config.ocr.lang)
            elements = estimate_visual_attributes(elements, norm_path)
            page_progress(0.75, f"ページ {i + 1}/{n_pages} OCR 済み")

            if elements and config.llm_correction.enabled:
                page_progress(0.8, f"ページ {i + 1}/{n_pages} LLM 補正中…")
                provider = select_llm_provider(config)
                if provider:
                    try:
                        elements = correct_texts(
                            elements, provider, config.get_env,
                            model_anthropic=config.models.anthropic,
                            model_gemini=config.models.gemini,
                        )
                    except Exception as e:
                        logger.warning("LLM correction failed for page %s: %s", i, e)
            page_progress(1.0, f"ページ {i + 1}/{n_pages} 完了")

            pages_data.append((layer_paths, elements))

        if output_path is None:
            output_path = output_dir / f"{pdf_path.stem}.pptx"
        output_path = Path(output_path)

        report(0.95, "PPTX を生成中…")
        build_pptx_multi_slides(
            pages_data,
            output_path,
            slide_width_inches=config.output.slide_width_inches,
            slide_height_inches=config.output.slide_height_inches,
        )
        return str(output_path)
    finally:
        if config.clean_temp:
            cleanup_temp_files([work_dir], clean=True)


def run_batch(
    input_paths: list[str | Path],
    config: AppConfig,
    output_dir: Path | None = None,
) -> list[str]:
    """
    複数入力（画像・PDF）を順に処理し、各入力に対して 1 つずつ .pptx を出力する。

    Returns:
        生成した .pptx のファイルパスのリスト
    """
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        _, output_dir, _ = ensure_directories_from_config(config)

    results: list[str] = []
    for path in input_paths:
        path = Path(path)
        if not path.exists():
            logger.warning("スキップ（存在しません）: %s", path)
            continue
        try:
            if path.suffix.lower() == ".pdf":
                out = run_pdf(path, config, output_path=output_dir / f"{path.stem}.pptx")
            else:
                out = run_single(path, config, output_path=output_dir / f"{path.stem}.pptx")
            results.append(out)
        except (FileNotFoundError, ValueError) as e:
            logger.warning("スキップ: %s — %s", path.name, e)
        except Exception as e:
            logger.warning("スキップ: %s — %s", path.name, e)
    return results


def collect_input_paths(directory: str | Path) -> list[Path]:
    """ディレクトリ内の対象画像・PDF を列挙する。"""
    from .image_utils import SUPPORTED_EXTENSIONS

    directory = Path(directory)
    if not directory.is_dir():
        return []
    paths: list[Path] = []
    for p in sorted(directory.iterdir()):
        if p.suffix.lower() in SUPPORTED_EXTENSIONS:
            paths.append(p)
        elif p.suffix.lower() == ".pdf":
            paths.append(p)
    return paths
