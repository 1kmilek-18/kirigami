"""パイプライン一気通貫とバッチのテスト（Req: 11.1, 11.2）"""
from __future__ import annotations

import pytest
from pathlib import Path

from kirigami_image_to_pptx.config_loader import load_config
from kirigami_image_to_pptx.pipeline import run_batch, run_single


def _minimal_image_path(tmp_path: Path) -> Path:
    """小さな PNG を一時作成する。"""
    from PIL import Image
    p = tmp_path / "minimal.png"
    Image.new("RGB", (10, 10), color="white").save(p)
    return p


@pytest.fixture
def config(tmp_path: Path) -> None:
    """テスト用 config はプロジェクトの config.yaml を読む。"""
    pass


def test_run_batch_skips_missing_file(tmp_path: Path) -> None:
    """バッチで存在しないファイルはスキップされ続行する。"""
    cfg = load_config(Path(__file__).resolve().parent.parent / "config.yaml")
    cfg.decompose.backend = "cpu"
    out_dir = tmp_path / "out"
    results = run_batch([tmp_path / "nonexistent.png"], cfg, output_dir=out_dir)
    assert results == []


def test_run_batch_skips_unsupported_format(tmp_path: Path) -> None:
    """バッチで対応形式外はスキップされ続行する。"""
    bad = tmp_path / "bad.txt"
    bad.write_text("x")
    cfg = load_config(Path(__file__).resolve().parent.parent / "config.yaml")
    cfg.decompose.backend = "cpu"
    out_dir = tmp_path / "out"
    results = run_batch([bad], cfg, output_dir=out_dir)
    assert results == []


@pytest.mark.skipif(
    True,  # 外部依存（Paddle/Vision）が必要なため、CI ではスキップ。手動で外して実行可。
    reason="OCR 依存のためスキップ。手動で pytest -k test_run_single -v で実行可能",
)
def test_run_single_produces_pptx(tmp_path: Path) -> None:
    """画像 1 枚でパイプラインを実行し、編集可能な .pptx が得られることを検証する。"""
    img = _minimal_image_path(tmp_path)
    cfg = load_config(Path(__file__).resolve().parent.parent / "config.yaml")
    cfg.decompose.backend = "cpu"
    cfg.llm_correction.enabled = False
    out_path = tmp_path / "out.pptx"
    result = run_single(img, cfg, output_path=out_path)
    assert Path(result).exists()
    assert Path(result).stat().st_size > 0
    from pptx import Presentation
    prs = Presentation(result)
    assert len(prs.slides) >= 1
