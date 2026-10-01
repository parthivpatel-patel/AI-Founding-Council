"""Build the provider set from the environment. Construction does not call a network."""

from __future__ import annotations

from pathlib import Path

from app.config import env_value
from app.providers.anthropic import AnthropicProvider
from app.providers.base import ProviderConfigError
from app.providers.cursor import CursorProvider
from app.providers.gemini import GeminiProvider
from app.providers.nvidia import NvidiaProvider
from app.providers.openai import OpenAIProvider
from app.providers.router import DEFAULT_ROUTES, PROVIDER_NAMES, ModelRouter
from app.providers.xai import XAIProvider

_ROUTE_ENV = {
    "strategy": "STRATEGIST_PROVIDER",
    "research": "RESEARCHER_PROVIDER",
    "red_team": "RED_TEAM_PROVIDER",
    "contrarian": "CONTRARIAN_PROVIDER",
    "cto": "CTO_PROVIDER",
}


def router_from_env(root: Path) -> ModelRouter:
    providers = {
        "openai": OpenAIProvider.from_env(),
        "anthropic": AnthropicProvider.from_env(),
        "gemini": GeminiProvider.from_env(),
        "xai": XAIProvider.from_env(),
        "nvidia": NvidiaProvider.from_env(),
        "cursor": CursorProvider.from_env(root),
    }
    routes: dict[str, str] = {}
    for task, env_name in _ROUTE_ENV.items():
        configured = env_value(env_name) or DEFAULT_ROUTES[task]
        if configured not in PROVIDER_NAMES:
            raise ProviderConfigError(f"{env_name} must be one of {', '.join(PROVIDER_NAMES)}")
        routes[task] = configured
    return ModelRouter(providers, routes)
