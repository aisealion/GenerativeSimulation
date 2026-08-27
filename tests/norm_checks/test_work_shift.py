"""Tests for work_shift norm."""

import pytest
from norms.work_shift import WorkShiftNorm
from engine.norms.context import HarvestContext
from engine.norms.base import NormDecision


def make_context(stock_before=200, runtime=None):
    """Build a minimal HarvestContext for testing."""
    return HarvestContext(
        config={},
        fluents=[],
        runtime=runtime or {},
        agents={},
        round_number=1,
        stock_before=stock_before,
    )


class TestWorkShiftNorm:
    def test_type_name(self):
        norm = WorkShiftNorm("test", {})
        assert norm.type_name == "work_shift"

    def test_eligible_when_no_shift_pending(self):
        """Agent can fish when no work shift is pending."""
        norm = WorkShiftNorm("test", {"min_catch_kg": 1.0, "shift_trips": 2})
        context = make_context()
        assert norm.is_eligible(context, "agent_1") is True

    def test_ineligible_when_shift_pending(self):
        """Agent cannot fish when work shift is pending."""
        norm = WorkShiftNorm("test", {"min_catch_kg": 1.0, "shift_trips": 2})
        context = make_context(runtime={"norms": {"test": {"agent_1": {"trips_remaining": 2}}}})
        assert norm.is_eligible(context, "agent_1") is False

    def test_shift_counts_down_each_round(self):
        """Shift counter decrements each round."""
        norm = WorkShiftNorm("test", {"min_catch_kg": 1.0, "shift_trips": 2})
        runtime = {"norms": {"test": {"agent_1": {"trips_remaining": 2}}}}
        
        # First round - still has 2 trips, becomes 1 after check
        context = make_context(runtime=runtime.copy())
        context.runtime["norms"]["test"] = {"agent_1": {"trips_remaining": 2}}
        assert norm.is_eligible(context, "agent_1") is False
        assert norm._shift_state(context, "agent_1")["trips_remaining"] == 1
        
        # Second round - has 1 trip, becomes 0 after check
        context2 = make_context(runtime={"norms": {"test": {"agent_1": {"trips_remaining": 1}}}})
        assert norm.is_eligible(context2, "agent_1") is False
        assert norm._shift_state(context2, "agent_1")["trips_remaining"] == 0
        
        # Third round - has 0 trips, eligible and stays 0
        context3 = make_context(runtime={"norms": {"test": {"agent_1": {"trips_remaining": 0}}}})
        assert norm.is_eligible(context3, "agent_1") is True
        assert norm._shift_state(context3, "agent_1")["trips_remaining"] == 0

    def test_describe_when_no_shift(self):
        """No description when no shift is pending."""
        norm = WorkShiftNorm("test", {})
        context = make_context()
        assert norm.describe(context, "agent_1") is None

    def test_describe_when_shift_pending(self):
        """Description explains the work shift when pending."""
        norm = WorkShiftNorm("test", {})
        context = make_context(runtime={"norms": {"test": {"agent_1": {"trips_remaining": 2}}}})
        desc = norm.describe(context, "agent_1")
        assert "community shift" in desc
        assert "2" in desc or "two" in desc.lower()

    def test_on_agent_settled_triggers_shift_for_low_catch(self):
        """Work shift is triggered when agent catches less than min_catch_kg."""
        norm = WorkShiftNorm("test", {"min_catch_kg": 1.0, "shift_trips": 2})
        context = make_context()
        decision = NormDecision.allow(kept_kg=0.5)
        
        norm.on_agent_settled(context, "agent_1", decision, harvested_kg=0.5)
        
        assert norm._shift_state(context, "agent_1")["trips_remaining"] == 2

    def test_on_agent_settled_no_shift_for_sufficient_catch(self):
        """No work shift triggered when agent catches at least min_catch_kg."""
        norm = WorkShiftNorm("test", {"min_catch_kg": 1.0, "shift_trips": 2})
        context = make_context()
        decision = NormDecision.allow(kept_kg=1.5)
        
        norm.on_agent_settled(context, "agent_1", decision, harvested_kg=1.5)
        
        assert norm._shift_state(context, "agent_1")["trips_remaining"] == 0

    def test_on_agent_settled_no_shift_at_exact_threshold(self):
        """No work shift triggered when agent catches exactly min_catch_kg."""
        norm = WorkShiftNorm("test", {"min_catch_kg": 1.0, "shift_trips": 2})
        context = make_context()
        decision = NormDecision.allow(kept_kg=1.0)
        
        norm.on_agent_settled(context, "agent_1", decision, harvested_kg=1.0)
        
        assert norm._shift_state(context, "agent_1")["trips_remaining"] == 0

    def test_default_params(self):
        """Default params are min_catch_kg=1.0 and shift_trips=2."""
        norm = WorkShiftNorm("test", {})
        context = make_context()
        decision = NormDecision.allow(kept_kg=0.5)
        
        norm.on_agent_settled(context, "agent_1", decision, harvested_kg=0.5)
        
        # Should trigger with default 2 trips
        assert norm._shift_state(context, "agent_1")["trips_remaining"] == 2

    def test_evaluate_allows_all(self):
        """evaluate() always allows the proposed kg."""
        norm = WorkShiftNorm("test", {})
        context = make_context()
        decision = norm.evaluate(context, "agent_1", raw_kg=10, proposed_kg=8)
        assert decision.kept_kg == 8
        assert not decision.violated
