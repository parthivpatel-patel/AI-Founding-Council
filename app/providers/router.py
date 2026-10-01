"""Select a provider for a task. Phase 2 has one route."""

from __future__ import annotations

from collections.abc import Mapping

from app.providers.base import ModelProvider, ProviderConfigError


class ModelRouter:
    def __init__(self, providers: Mapping[str, ModelProvider]) -> None:
        self._providers = dict(providers)

    def select(self, task: str) -> ModelProvider:
        if task == "strategy":
            provider = self._providers.get("openai")
            if provider is None:
                raise ProviderConfigError("No provider is configured for strategy")
            return provider
        raise ProviderConfigError(f"No provider route exists for task {task!r}")
