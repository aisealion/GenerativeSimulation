"""Tests for Round 1: Catch Cap Norm (5kg limit per trip).

Policy: Each fisher may take no more than 5 kg per trip.
"""

import pytest

from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.catch_cap import CatchCapNorm


def _context(stock_kg=300.0, round_number=1):
    """Create a test context."""
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": {"stock_kg": stock_kg, "rounds": []},
        "agents": {},
        "round_number": round_number,
    })


def test_catch_cap_allows_under_limit():
    """R1: Catch at or below 5kg is allowed."""
    norm = CatchCapNorm(key="cap", params={"limit_kg": 5.0})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=3.0, proposed_kg=3.0)

    assert decision.kept_kg == 3.0
    assert not decision.violated
    assert decision.sanction is None


def test_catch_cap_trims_over_limit():
    """R1: Catch over 5kg is trimmed to 5kg."""
    norm = CatchCapNorm(key="cap", params={"limit_kg": 5.0})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=8.0, proposed_kg=8.0)

    assert decision.kept_kg == 5.0
    assert decision.violated
    assert decision.sanction == "over_cap"
    assert "5kg limit" in decision.note


def test_catch_cap_exactly_at_limit():
    """R1: Catch exactly at 5kg is allowed."""
    norm = CatchCapNorm(key="cap", params={"limit_kg": 5.0})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=5.0, proposed_kg=5.0)

    assert decision.kept_kg == 5.0
    assert not decision.violated


def test_catch_cap_provides_description():
    """R1: Catch cap describes the constraint to agents."""
    norm = CatchCapNorm(key="cap", params={"limit_kg": 5.0})
    description = norm.describe(_context(), "agent_0")

    assert description is not None
    assert "5kg" in description
    assert "limit" in description


def test_catch_cap_default_limit():
    """R1: Default limit is 5kg when not specified."""
    norm = CatchCapNorm(key="cap", params={})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=6.0, proposed_kg=6.0)

    assert decision.kept_kg == 5.0
    assert decision.violated
