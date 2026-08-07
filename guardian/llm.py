"""Helpers for configuring LiteLLM and constructing the GUARDIAN pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .settings import settings


@dataclass
class LMConfig:
    model: Optional[str] = None
    temperature: Optional[float] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None

    @classmethod
    def from_settings(cls) -> "LMConfig":
        return cls(
            model=settings.model,
            temperature=settings.temperature,
            api_base=settings.api_base,
            api_key=settings.api_key,
        )


class LiteLLMClient:
    def __init__(self, config: LMConfig) -> None:
        if config.model is None or config.temperature is None:
            raise ValueError("LMConfig requires at least model and temperature")
        self.config = config

    def __call__(self, prompt: str) -> str:
        from litellm import completion

        kwargs = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.config.temperature,
        }
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key

        response = completion(**kwargs)
        choice = response.choices[0]
        return choice.message.content or ""


def build_lm(config: Optional[LMConfig] = None):
    cfg = config or LMConfig.from_settings()
    return LiteLLMClient(cfg)


def build_pipeline(config: Optional[LMConfig] = None):
    from .pipeline import GUARDIANPipeline

    lm = build_lm(config)
    return GUARDIANPipeline(lm=lm)
