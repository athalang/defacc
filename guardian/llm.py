"""Helpers for configuring dspy and constructing the IRENE pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import dspy

from .pipeline import GUARDIANPipeline
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


def build_lm(config: Optional[LMConfig] = None) -> dspy.LM:
    cfg = config or LMConfig.from_settings()
    if cfg.model is None or cfg.temperature is None:
        raise ValueError("LMConfig requires at least model and temperature")
    return dspy.LM(
        model=cfg.model,
        api_base=cfg.api_base,
        temperature=cfg.temperature,
        api_key=cfg.api_key,
    )


def build_pipeline(config: Optional[LMConfig] = None) -> IRENEPipeline:
    lm = build_lm(config)
    dspy.configure(lm=lm)
    return IRENEPipeline(lm=lm)
