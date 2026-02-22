"""
PDF のページ単位画像変換（Req: 1.2）

複数ページ PDF をページごとに画像へ変換し、各ページを個別に処理可能にする。
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

import fitz  # PyMuPDF

try:
    from .debug_log import log as debug_log
except Exception:
    def debug_log(_: str) -> None: pass


def pdf_to_images(
    pdf_path: str | Path,
    dpi: int = 120,
    temp_dir: str | Path | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[str]:
    """
    PDF をページ単位の画像に変換する。

    Args:
        pdf_path: PDF ファイルパス
        dpi: レンダリング解像度（低いほど高速、120 前後を推奨）
        temp_dir: 出力先の一時ディレクトリ。None の場合はシステムの一時ディレクトリを使用
        progress_callback: 進捗通知 (current_page_1based, total_pages) のコールバック

    Returns:
        各ページの画像ファイルパス（PNG）のリスト。先頭が 1 ページ目。
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path}")

    if temp_dir is not None:
        out_dir = Path(temp_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        keep = True
    else:
        out_dir = Path(tempfile.mkdtemp(prefix="kirigami_pdf_"))
        keep = False

    result_paths: list[str] = []
    try:
        doc = fitz.open(pdf_path)
        try:
            n_pages = len(doc)
            for i, page in enumerate(doc):
                debug_log(f"pdf_to_images: page {i+1}/{n_pages} get_pixmap start")
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                out_path = out_dir / f"page_{i:04d}.png"
                pix.save(str(out_path))
                debug_log(f"pdf_to_images: page {i+1}/{n_pages} save done")
                result_paths.append(str(out_path))
                if progress_callback is not None:
                    progress_callback(i + 1, n_pages)
        finally:
            doc.close()
    except Exception:
        if not keep and out_dir.exists():
            import shutil
            shutil.rmtree(out_dir, ignore_errors=True)
        raise

    return result_paths
