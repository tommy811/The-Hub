# scripts/tests/pipeline/test_resolver_recursive.py
import os
from unittest.mock import MagicMock, patch
import pytest

from schemas import InputContext, DiscoveryResultV2, TextMention, DiscoveredUrl
from pipeline.resolver import ResolverResult, resolve_seed
from pipeline.budget import BudgetTracker
from pipeline.classifier import Classification


def _mk_ctx(**overrides):
    base = dict(
        handle="alice", platform="instagram", display_name="Alice",
        bio="", follower_count=50000, avatar_url="https://cdn/a.jpg",
        external_urls=[], source_note="test",
    )
    base.update(overrides)
    return InputContext(**base)


def test_resolver_module_exposes_max_depth_constant():
    from pipeline import resolver
    assert hasattr(resolver, "MAX_DEPTH")
    assert isinstance(resolver.MAX_DEPTH, int)
    assert resolver.MAX_DEPTH >= 2


def test_resolver_module_exposes_recursive_gemini_constant():
    from pipeline import resolver
    assert hasattr(resolver, "RECURSIVE_GEMINI")
    assert isinstance(resolver.RECURSIVE_GEMINI, bool)
