"""
テキスト補正（LLM）（Req: 4.1–4.4）

OCR 結果の誤認識を文脈に基づいて補正する。座標は維持する。
複数プロバイダ（Claude / Gemini / Ollama）の優先順位とフォールバックに対応。
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from .models import TextElement

logger = logging.getLogger(__name__)

_CORRECTION_SYSTEM = """You are correcting OCR (optical character recognition) output. 
Given a list of text lines in order, fix any recognition errors (wrong characters, spacing, line breaks). 
Preserve the exact number and order of lines. Return ONLY the corrected lines, one per line, no numbering or extra text."""


def _build_lines_prompt(elements: list[TextElement]) -> str:
    """要素リストから LLM 用の行テキストを組み立てる。"""
    return "\n".join(el.get("text", "") or "" for el in elements)


def _parse_corrected_lines(response_text: str, expected_count: int) -> list[str]:
    """LLM 応答から行リストを抽出する。"""
    text = (response_text or "").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # 番号付きリスト (1. xxx) を除去
    cleaned = []
    for ln in lines:
        m = re.match(r"^\d+[\.\)]\s*", ln)
        if m:
            ln = ln[m.end() :].strip()
        cleaned.append(ln)
    if len(cleaned) >= expected_count:
        return cleaned[:expected_count]
    # 足りない場合は元の行数に合わせてパディング
    while len(cleaned) < expected_count:
        cleaned.append("")
    return cleaned[:expected_count]


def _correct_with_anthropic(
    elements: list[TextElement],
    get_env: callable,
    model_id: str,
) -> list[TextElement]:
    """Claude (Anthropic) で補正する。"""
    from anthropic import Anthropic

    api_key = get_env("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set.")
    client = Anthropic(api_key=api_key)
    prompt = _build_lines_prompt(elements)
    msg = client.messages.create(
        model=model_id,
        max_tokens=4096,
        system=_CORRECTION_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = ""
    for block in msg.content:
        if hasattr(block, "text"):
            response_text += block.text
    corrected = _parse_corrected_lines(response_text, len(elements))
    return [
        TextElement(
            text=corrected[i] if i < len(corrected) else (el.get("text") or ""),
            bbox=el.get("bbox", (0, 0, 0, 0)),
            confidence=el.get("confidence", 0.0),
            font_size_pt=el.get("font_size_pt"),
            font_color=el.get("font_color"),
            is_bold=el.get("is_bold"),
        )
        for i, el in enumerate(elements)
    ]


def _correct_with_google(
    elements: list[TextElement],
    get_env: callable,
    model_id: str,
) -> list[TextElement]:
    """Gemini (Google) で補正する。"""
    import google.generativeai as genai

    api_key = get_env("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set.")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_id)
    prompt = _build_lines_prompt(elements)
    response = model.generate_content(
        _CORRECTION_SYSTEM + "\n\nInput:\n" + prompt,
        generation_config={"max_output_tokens": 4096},
    )
    response_text = getattr(response, "text", None) or ""
    if not response_text and response.candidates and response.candidates[0].content.parts:
        response_text = response.candidates[0].content.parts[0].text
    corrected = _parse_corrected_lines(response_text, len(elements))
    return [
        TextElement(
            text=corrected[i] if i < len(corrected) else (el.get("text") or ""),
            bbox=el.get("bbox", (0, 0, 0, 0)),
            confidence=el.get("confidence", 0.0),
            font_size_pt=el.get("font_size_pt"),
            font_color=el.get("font_color"),
            is_bold=el.get("is_bold"),
        )
        for i, el in enumerate(elements)
    ]


def _correct_with_ollama(
    elements: list[TextElement],
) -> list[TextElement]:
    """Ollama ローカルで補正する。"""
    try:
        import requests
    except ImportError:
        raise ImportError("requests is required for Ollama. pip install requests") from None

    prompt = _build_lines_prompt(elements)
    body = {
        "model": "llama3.2",
        "prompt": _CORRECTION_SYSTEM + "\n\nInput:\n" + prompt,
        "stream": False,
    }
    try:
        r = requests.post("http://localhost:11434/api/generate", json=body, timeout=120)
        r.raise_for_status()
        data = r.json()
        response_text = data.get("response", "")
    except requests.RequestException as e:
        logger.warning("Ollama request failed: %s", e)
        return elements
    corrected = _parse_corrected_lines(response_text, len(elements))
    return [
        TextElement(
            text=corrected[i] if i < len(corrected) else (el.get("text") or ""),
            bbox=el.get("bbox", (0, 0, 0, 0)),
            confidence=el.get("confidence", 0.0),
            font_size_pt=el.get("font_size_pt"),
            font_color=el.get("font_color"),
            is_bold=el.get("is_bold"),
        )
        for i, el in enumerate(elements)
    ]


def correct_texts(
    elements: list[TextElement],
    provider: Literal["anthropic", "google", "ollama"],
    get_env: callable | None = None,
    *,
    model_anthropic: str = "claude-sonnet-4-6",
    model_gemini: str = "gemini-3-pro-preview",
) -> list[TextElement]:
    """
    OCR 結果のテキストを文脈に基づいて補正する。bbox 等は変更しない。

    Args:
        elements: 補正前の TextElement リスト
        provider: 使用するプロバイダ（anthropic / google / ollama）
        get_env: 環境変数取得関数。None の場合は os.environ.get
        model_anthropic: Claude モデル ID（config.models.anthropic）
        model_gemini: Gemini モデル ID（config.models.gemini）

    Returns:
        補正後の TextElement リスト（座標・属性は維持）
    """
    import os

    if not elements:
        return elements
    get_env = get_env or (lambda k, default="": os.environ.get(k, default))

    if provider == "anthropic":
        return _correct_with_anthropic(elements, get_env, model_anthropic)
    if provider == "google":
        return _correct_with_google(elements, get_env, model_gemini)
    if provider == "ollama":
        return _correct_with_ollama(elements)
    raise ValueError(f"Unknown provider: {provider}. Use anthropic, google, or ollama.")
