"""Pluggable trading-agent framework."""
from .base import Strategy, StrategyContext, StrategyDecision
from .registry import build_strategy

__all__ = ["Strategy", "StrategyContext", "StrategyDecision", "build_strategy"]
