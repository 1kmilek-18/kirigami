"""
設定ファイルと環境変数の読込（Req: 7.1, 7.2）

- config.yaml からレイヤー数・バックエンド・OCR 方式・LLM 設定・出力先等を読む。
- API キー等は .env および環境変数のみから読む（config.yaml には含めない）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv

# 参照する .env パス（優先順: 1. 自プロジェクト .env  2. presentation-maker .env）
_KIRIGAMI_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATHS = [
    _KIRIGAMI_ROOT / ".env",
    _KIRIGAMI_ROOT.parent / "presentation-maker" / ".env",
]


def _load_env() -> None:
    """自プロジェクトの .env を読んでから、presentation-maker の .env を読む（未設定のキーのみ埋まる）。"""
    for p in _ENV_PATHS:
        if p.exists():
            load_dotenv(p, override=False)
    return None


# 起動時に .env を読込（環境変数で上書き可能）
_load_env()


@dataclass
class PathsConfig:
    """入出力・一時ディレクトリのパス設定"""
    input_dir: str = "input"
    output_dir: str = "output"
    temp_dir: str = "temp"


@dataclass
class DecomposeConfig:
    """レイヤー分解の設定"""
    backend: Literal["api", "cpu"] = "api"
    num_layers: int = 4


@dataclass
class ImageConfig:
    """画像前処理の設定"""
    max_resolution: int = 640
    pdf_dpi: int = 120  # PDF→画像の解像度（低いほど高速、150 前後で画質と速度のバランス）


@dataclass
class OCRConfig:
    """OCR の設定"""
    method: Literal["paddle", "vision"] = "paddle"
    lang: str = "japan"


@dataclass
class ModelsConfig:
    """API モデル ID の設定"""
    gemini: str = "gemini-3-pro-preview"
    anthropic: str = "claude-sonnet-4-6"


@dataclass
class LLMCorrectionConfig:
    """LLM 補正の設定"""
    enabled: bool = True
    provider_fallback: list[str] = field(default_factory=lambda: ["anthropic", "google", "ollama"])


@dataclass
class OutputConfig:
    """PPTX 出力の設定"""
    slide_width_inches: float = 13.333
    slide_height_inches: float = 7.5


@dataclass
class AppConfig:
    """
    アプリケーション全体の設定。
    レイヤー数・バックエンド・OCR 方式・LLM 設定・出力先等は config.yaml から、
    API キーは環境変数のみから取得する。
    """
    paths: PathsConfig = field(default_factory=PathsConfig)
    decompose: DecomposeConfig = field(default_factory=DecomposeConfig)
    image: ImageConfig = field(default_factory=ImageConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    llm_correction: LLMCorrectionConfig = field(default_factory=LLMCorrectionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    clean_temp: bool = True
    _config_path: Path | None = field(default=None, repr=False)

    @property
    def base_path(self) -> Path | None:
        """config ファイルがあるディレクトリ（相対パス解決の基準）"""
        if self._config_path is None:
            return None
        return self._config_path.parent

    def get_env(self, key: str, default: str = "") -> str:
        """
        API キー等は環境変数のみから取得する。
        presentation-maker の .env にあるキー名の別名も参照する:
        - GOOGLE_API_KEY → 無ければ GEMINI_API_KEY
        - ANTHROPIC_API_KEY → 無ければ CLAUDE_API_KEY
        """
        v = os.environ.get(key, default)
        if not (v or "").strip() and key == "GOOGLE_API_KEY":
            v = os.environ.get("GEMINI_API_KEY", default)
        if not (v or "").strip() and key == "ANTHROPIC_API_KEY":
            v = os.environ.get("CLAUDE_API_KEY", default)
        return (v or "").strip()


def _parse_paths(data: dict) -> PathsConfig:
    p = data.get("paths") or {}
    return PathsConfig(
        input_dir=p.get("input_dir", "input"),
        output_dir=p.get("output_dir", "output"),
        temp_dir=p.get("temp_dir", "temp"),
    )


def _parse_decompose(data: dict) -> DecomposeConfig:
    d = data.get("decompose") or {}
    backend = d.get("backend", "api")
    if backend not in ("api", "cpu"):
        backend = "api"
    return DecomposeConfig(
        backend=backend,
        num_layers=max(3, min(10, int(d.get("num_layers", 4)))),
    )


def _parse_image(data: dict) -> ImageConfig:
    i = data.get("image") or {}
    return ImageConfig(
        max_resolution=int(i.get("max_resolution", 640)),
        pdf_dpi=max(72, min(300, int(i.get("pdf_dpi", 120)))),
    )


def _parse_ocr(data: dict) -> OCRConfig:
    o = data.get("ocr") or {}
    method = o.get("method", "paddle")
    if method not in ("paddle", "vision"):
        method = "paddle"
    return OCRConfig(method=method, lang=str(o.get("lang", "japan")))


def _parse_models(data: dict) -> ModelsConfig:
    m = data.get("models") or {}
    return ModelsConfig(
        gemini=str(m.get("gemini", "gemini-3-pro-preview")),
        anthropic=str(m.get("anthropic", "claude-sonnet-4-6")),
    )


def _parse_llm_correction(data: dict) -> LLMCorrectionConfig:
    l = data.get("llm_correction") or {}
    fallback = l.get("provider_fallback") or ["anthropic", "google", "ollama"]
    if not isinstance(fallback, list):
        fallback = ["anthropic", "google", "ollama"]
    return LLMCorrectionConfig(
        enabled=bool(l.get("enabled", True)),
        provider_fallback=[str(x) for x in fallback],
    )


def _parse_output(data: dict) -> OutputConfig:
    o = data.get("output") or {}
    return OutputConfig(
        slide_width_inches=float(o.get("slide_width_inches", 13.333)),
        slide_height_inches=float(o.get("slide_height_inches", 7.5)),
    )


def load_config(config_path: str | Path = "config.yaml") -> AppConfig:
    """
    config.yaml を読み込み AppConfig を返す。
    API キーはこの関数では読まない。利用側で cfg.get_env("FAL_KEY") 等で取得する。
    """
    path = Path(config_path)
    raw: dict = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    resolved_path = path.resolve() if path.exists() else None
    return AppConfig(
        paths=_parse_paths(raw),
        decompose=_parse_decompose(raw),
        image=_parse_image(raw),
        ocr=_parse_ocr(raw),
        models=_parse_models(raw),
        llm_correction=_parse_llm_correction(raw),
        output=_parse_output(raw),
        clean_temp=bool(raw.get("clean_temp", True)),
        _config_path=resolved_path,
    )


def ensure_directories_from_config(config: AppConfig) -> tuple[Path, Path, Path]:
    """
    設定に従い入力・出力・一時ディレクトリの存在を保証する。
    config_loader の利用側で paths を import せずに使えるようにする。
    """
    from .paths import ensure_directories
    base = config.base_path
    return ensure_directories(
        config.paths.input_dir,
        config.paths.output_dir,
        config.paths.temp_dir,
        base_path=base,
    )
