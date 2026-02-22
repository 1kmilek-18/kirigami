"""入力検証・エラーメッセージのテスト（Req: 10.1）"""
from __future__ import annotations

import pytest
from pathlib import Path

from kirigami_image_to_pptx.errors import validate_input_path


def test_validate_input_path_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent.png"
    with pytest.raises(FileNotFoundError) as exc:
        validate_input_path(missing)
    assert "見つかりません" in str(exc.value) or "not found" in str(exc.value).lower()


def test_validate_input_path_unsupported_format(tmp_path: Path) -> None:
    bad = tmp_path / "file.txt"
    bad.write_text("x")
    with pytest.raises(ValueError) as exc:
        validate_input_path(bad)
    assert ".txt" in str(exc.value) or "対応" in str(exc.value)


def test_validate_input_path_accepts_image(tmp_path: Path) -> None:
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not installed")
    img = tmp_path / "test.png"
    Image.new("RGB", (2, 2), color="red").save(img)
    validate_input_path(img)


def test_validate_input_path_accepts_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.0 minimal")
    validate_input_path(pdf)
