"""CLI オプションと設定のテスト（Req: 11.2）"""
from __future__ import annotations

from pathlib import Path

import pytest

from kirigami_image_to_pptx.cli import _apply_cli_overrides, parse_args
from kirigami_image_to_pptx.config_loader import load_config


def test_parse_args_defaults() -> None:
    args = parse_args([])
    assert args.input is None
    assert args.layers is None
    assert args.backend is None
    assert args.ocr is None
    assert args.no_llm_correct is False


def test_parse_args_input_and_options() -> None:
    args = parse_args(["input.png", "--layers", "5", "--backend", "cpu", "--no-llm-correct"])
    assert args.input is not None and args.input.name == "input.png"
    assert args.layers == 5
    assert args.backend == "cpu"
    assert args.no_llm_correct is True


def test_apply_cli_overrides() -> None:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    if not config_path.exists():
        pytest.skip("config.yaml not found")
    config = load_config(config_path)
    args = parse_args(["--layers", "6", "--backend", "cpu", "--ocr", "vision", "--no-llm-correct"])
    _apply_cli_overrides(config, args)
    assert config.decompose.num_layers == 6
    assert config.decompose.backend == "cpu"
    assert config.ocr.method == "vision"
    assert config.llm_correction.enabled is False
