"""
複数 LLM/API プロバイダの優先順位とフォールバック順の適用（Req: 7.3）

config の provider_fallback に従い、利用可能なプロバイダを先頭から選択する。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .config_loader import AppConfig

logger = logging.getLogger(__name__)

# プロバイダ別の環境変数キー（キーが設定されていれば利用可能とみなす）
_PROVIDER_ENV_KEYS: dict[str, list[str]] = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "google": ["GOOGLE_API_KEY"],
    "ollama": [],  # ローカルはキー不要。接続可能かは実行時チェックに委譲
}


def _is_provider_available(provider: str, get_env: Callable[[str], str]) -> bool:
    keys = _PROVIDER_ENV_KEYS.get(provider, [])
    if not keys:
        # ollama 等はここでは「常に試行可能」としておく
        return True
    return any(bool(get_env(k)) for k in keys)


def select_llm_provider(config: AppConfig) -> str | None:
    """
    config.llm_correction.provider_fallback の順で、
    利用可能な（API キーが設定されている）プロバイダを返す。
    利用可能なものがなければ None。
    """
    if not config.llm_correction.enabled:
        return None
    get_env = config.get_env
    for name in config.llm_correction.provider_fallback:
        if _is_provider_available(name, get_env):
            return name
    logger.warning(
        "No LLM provider available (checked order: %s). Disable llm_correction or set API keys.",
        config.llm_correction.provider_fallback,
    )
    return None
