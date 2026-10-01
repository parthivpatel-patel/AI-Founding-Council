"""Select a provider for a task. Routes are configurable."""

from __future__ import annotations

from collections.abc import Mapping

from app.providers.base import ModelProvider, ProviderConfigError

DEFAULT_ROUTES = {
    "strategy": "openai",
    "research": "gemini",
    "red_team": "anthropic",
    "contrarian": "xai",
}

PROVIDER_NAMES = ("openai", "anthropic", "gemini", "xai", "nvidia", "cursor")


class ModelRouter:
    def __init__(
        self,
        providers: Mapping[str, ModelProvider],
        routes: Mapping[str, str] | None = None,
    ) -> None:
        self._providers = dict(providers)
        self._routes = dict(DEFAULT_ROUTES if routes is None else routes)

    def select(self, task: str) -> ModelProvider:
        provider_name = self._routes.get(task)
        if provider_name is None:
            raise ProviderConfigError(f"No provider route exists for task {task!r}")
        if provider_name not in PROVIDER_NAMES:
            raise ProviderConfigError(f"Unknown provider {provider_name!r}")
        provider = self._providers.get(provider_name)
        if provider is None:
            raise ProviderConfigError(f"No provider is configured for {task}")
        return provider
