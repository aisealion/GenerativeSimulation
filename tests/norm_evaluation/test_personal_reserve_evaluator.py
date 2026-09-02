"""
Independent norm-evaluator tests for personal_reserve norm.

These tests verify ALL requirements from state/norm_specs/round_4.md
without referencing the implementer's test file.
"""

import pytest
from engine.norms.context import HarvestContext
from norms.personal_reserve import PersonalReserveNorm
from engine.norms.base import NormDecision


def make_context(payoff_data=None, stock_kg=100.0):
    """Helper to create a HarvestContext with given payoff data."""
    runtime = {"stock_kg": stock_kg}
    if payoff_data is not None:
        runtime["payoff"] = payoff_data
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": runtime,
        "agents": {},
        "round_number": 1,
    })


# =============================================================================
# CORE FUNCTIONALITY REQUIREMENTS
# =============================================================================

def test_norm_plugin_exists():
    """REQ: Norm plugin personal_reserve.py exists in norms/ directory."""
    import os
    assert os.path.exists("norms/personal_reserve.py")


def test_norm_type_registered():
    """REQ: Norm type is registered as 'personal_reserve'."""
    norm = PersonalReserveNorm(key="test", params={})
    assert norm.type_name == "personal_reserve"


def test_norm_reads_from_payoff():
    """REQ: Norm uses runtime['payoff'][agent_id] to read agent's personal reserve."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 10.0})
    # Should be able to read the payoff value
    reserve = norm._get_reserve(context, "agent_0")
    assert reserve == 10.0


def test_default_minimum_is_5kg():
    """REQ: Default minimum reserve is 5kg (configurable via min_reserve_kg param)."""
    norm = PersonalReserveNorm(key="test", params={})
    assert norm._get_min_reserve() == 5.0


def test_configurable_minimum():
    """REQ: Minimum reserve is configurable via min_reserve_kg param."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 10.0})
    assert norm._get_min_reserve() == 10.0


# =============================================================================
# ELIGIBILITY REQUIREMENTS
# =============================================================================

def test_eligible_at_exact_minimum():
    """REQ: is_eligible() returns True when agent's reserve >= min_reserve_kg (at minimum)."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 5.0})
    assert norm.is_eligible(context, "agent_0") is True


def test_eligible_above_minimum():
    """REQ: is_eligible() returns True when agent's reserve >= min_reserve_kg (above minimum)."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 7.5})
    assert norm.is_eligible(context, "agent_0") is True


def test_ineligible_below_minimum():
    """REQ: is_eligible() returns False when agent's reserve < min_reserve_kg."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 4.9})
    assert norm.is_eligible(context, "agent_0") is False


def test_ineligible_zero_reserve():
    """REQ: Agents with no payoff entry are ineligible (treated as 0 reserve)."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 0.0})
    assert norm.is_eligible(context, "agent_0") is False


def test_ineligible_no_payoff_entry():
    """REQ: Agents with no payoff entry are ineligible (treated as 0 reserve)."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={})
    assert norm.is_eligible(context, "agent_0") is False


def test_ineligible_negative_reserve():
    """REQ: Agents with negative reserve are ineligible."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": -2.0})
    assert norm.is_eligible(context, "agent_0") is False


# =============================================================================
# DESCRIPTION REQUIREMENTS
# =============================================================================

def test_describe_shows_current_reserve_when_eligible():
    """REQ: describe() shows current reserve when eligible (e.g., 'Your personal reserve is Xkg...')."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 10.0})
    description = norm.describe(context, "agent_0")
    
    assert description is not None
    assert "10.0kg" in description or "10kg" in description
    assert "reserve" in description.lower()


def test_describe_shows_warning_when_ineligible():
    """REQ: describe() shows warning when ineligible with shortfall amount."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 3.0})
    description = norm.describe(context, "agent_0")
    
    assert description is not None
    assert "below" in description.lower() or "insufficient" in description.lower()
    # Should show shortfall of 2.0kg
    assert "2.0" in description or "2kg" in description


def test_describe_includes_minimum_required():
    """REQ: Description includes minimum required amount."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 10.0})
    description = norm.describe(context, "agent_0")
    
    assert "5" in description  # Should mention the 5kg minimum


def test_describe_includes_minimum_when_custom():
    """REQ: Description includes minimum required amount (custom value)."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 10.0})
    context = make_context(payoff_data={"agent_0": 15.0})
    description = norm.describe(context, "agent_0")
    
    assert "10" in description  # Should mention the 10kg minimum


# =============================================================================
# EVALUATE BEHAVIOR REQUIREMENTS
# =============================================================================

def test_evaluate_allows_when_eligible():
    """REQ: evaluate() allows the catch when eligible (returns NormDecision.allow())."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 10.0})
    decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
    
    assert decision.kept_kg == 15.0
    assert decision.violated is False


def test_evaluate_rejects_when_ineligible():
    """REQ: evaluate() rejects with violation when ineligible (returns NormDecision.reject())."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 3.0})
    decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
    
    assert decision.kept_kg == 0.0
    assert decision.violated is True


def test_evaluate_does_not_modify_catch_amount():
    """REQ: Catch amount is not modified (agents keep all they catch)."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 10.0})
    
    # Test with different catch amounts
    for catch in [1.0, 5.0, 10.0, 15.0, 20.0]:
        decision = norm.evaluate(context, "agent_0", raw_kg=catch, proposed_kg=catch)
        assert decision.kept_kg == catch, f"Expected {catch}kg but got {decision.kept_kg}kg"


def test_evaluate_preserves_full_amount():
    """REQ: Eligible agents can keep their full catch (no reduction)."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 100.0})  # Well above minimum
    
    decision = norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=50.0)
    assert decision.kept_kg == 50.0
    assert decision.violated is False


# =============================================================================
# CONFIGURATION REQUIREMENTS
# =============================================================================

def test_config_activates_norm():
    """REQ: Config in state/config.json activates the norm."""
    import json
    with open("state/config.json") as f:
        config = json.load(f)
    
    assert "norms" in config
    assert len(config["norms"]) > 0
    
    # Find personal_reserve norm
    personal_reserve_norms = [n for n in config["norms"] if n.get("type") == "personal_reserve"]
    assert len(personal_reserve_norms) > 0, "personal_reserve norm should be in config"


def test_config_specifies_type():
    """REQ: Config specifies 'type': 'personal_reserve'."""
    import json
    with open("state/config.json") as f:
        config = json.load(f)
    
    personal_reserve_norms = [n for n in config["norms"] if n.get("type") == "personal_reserve"]
    assert len(personal_reserve_norms) > 0


def test_config_specifies_min_reserve_kg():
    """REQ: Config specifies 'min_reserve_kg': 5.0."""
    import json
    with open("state/config.json") as f:
        config = json.load(f)
    
    personal_reserve_norms = [n for n in config["norms"] if n.get("type") == "personal_reserve"]
    assert len(personal_reserve_norms) > 0
    
    norm_config = personal_reserve_norms[0]
    assert "min_reserve_kg" in norm_config
    assert norm_config["min_reserve_kg"] == 5.0


# =============================================================================
# PER-AGENT TRACKING REQUIREMENTS
# =============================================================================

def test_per_agent_eligibility_independent():
    """REQ: Different agents have independent eligibility based on their own reserves."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={
        "rich_agent": 20.0,      # eligible
        "poor_agent": 2.0,       # ineligible
        "exact_agent": 5.0,      # eligible (at minimum)
        "zero_agent": 0.0,       # ineligible
    })
    
    assert norm.is_eligible(context, "rich_agent") is True
    assert norm.is_eligible(context, "poor_agent") is False
    assert norm.is_eligible(context, "exact_agent") is True
    assert norm.is_eligible(context, "zero_agent") is False


def test_per_agent_evaluate_independent():
    """REQ: evaluate() works independently for different agents."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={
        "rich_agent": 20.0,
        "poor_agent": 2.0,
    })
    
    # Rich agent should be allowed
    decision_rich = norm.evaluate(context, "rich_agent", raw_kg=10.0, proposed_kg=10.0)
    assert decision_rich.kept_kg == 10.0
    assert decision_rich.violated is False
    
    # Poor agent should be rejected
    decision_poor = norm.evaluate(context, "poor_agent", raw_kg=10.0, proposed_kg=10.0)
    assert decision_poor.kept_kg == 0.0
    assert decision_poor.violated is True


# =============================================================================
# EDGE CASES
# =============================================================================

def test_very_high_reserve():
    """Agents with very high reserves should be eligible."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 1000.0})
    assert norm.is_eligible(context, "agent_0") is True


def test_very_low_positive_reserve():
    """Agents with very low but positive reserves should be ineligible."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 0.01})
    assert norm.is_eligible(context, "agent_0") is False


def test_fractional_reserve_at_boundary():
    """Test boundary with fractional reserves."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    
    # Just below 5.0
    context = make_context(payoff_data={"agent_0": 4.999})
    assert norm.is_eligible(context, "agent_0") is False
    
    # Just above 5.0
    context = make_context(payoff_data={"agent_0": 5.001})
    assert norm.is_eligible(context, "agent_0") is True


def test_custom_minimum_eligibility():
    """Test eligibility with custom minimum values."""
    # With 10kg minimum
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 10.0})
    
    context = make_context(payoff_data={"agent_0": 9.9})
    assert norm.is_eligible(context, "agent_0") is False
    
    context = make_context(payoff_data={"agent_0": 10.0})
    assert norm.is_eligible(context, "agent_0") is True
    
    context = make_context(payoff_data={"agent_0": 15.0})
    assert norm.is_eligible(context, "agent_0") is True


# =============================================================================
# DESCRIPTION FORMATTING
# =============================================================================

def test_describe_includes_replenish_instruction_when_ineligible():
    """Ineligible description should tell agent they need to replenish."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 2.0})
    description = norm.describe(context, "agent_0")
    
    # Should contain instruction about replenishing
    assert "replenish" in description.lower() or "cannot fish" in description.lower() or "prohibited" in description.lower()


def test_describe_eligible_format():
    """Eligible description should be informative and positive."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 8.5})
    description = norm.describe(context, "agent_0")
    
    # Should not contain negative words
    assert "below" not in description.lower()
    assert "cannot" not in description.lower()
    assert "prohibited" not in description.lower()


# =============================================================================
# NORM DECISION TYPES
# =============================================================================

def test_eligible_returns_norm_decision_allow():
    """Verify eligible evaluate returns proper NormDecision.allow structure."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 10.0})
    decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)
    
    assert isinstance(decision, NormDecision)
    assert decision.violated is False
    assert decision.sanction is None


def test_ineligible_returns_norm_decision_reject():
    """Verify ineligible evaluate returns proper NormDecision.reject structure."""
    norm = PersonalReserveNorm(key="test", params={"min_reserve_kg": 5.0})
    context = make_context(payoff_data={"agent_0": 2.0})
    decision = norm.evaluate(context, "agent_0", raw_kg=5.0, proposed_kg=5.0)
    
    assert isinstance(decision, NormDecision)
    assert decision.kept_kg == 0.0
    assert decision.violated is True


# =============================================================================
# VERIFICATION SUMMARY
# =============================================================================

# These tests cover all 26 requirements from state/norm_specs/round_4.md:
#
# Core Functionality (4):
#   ✓ test_norm_plugin_exists
#   ✓ test_norm_type_registered  
#   ✓ test_norm_reads_from_payoff
#   ✓ test_default_minimum_is_5kg + test_configurable_minimum
#
# Eligibility (5):
#   ✓ test_eligible_at_exact_minimum
#   ✓ test_eligible_above_minimum
#   ✓ test_ineligible_below_minimum
#   ✓ test_ineligible_zero_reserve + test_ineligible_no_payoff_entry
#   ✓ test_ineligible_negative_reserve
#
# Descriptions (3):
#   ✓ test_describe_shows_current_reserve_when_eligible
#   ✓ test_describe_shows_warning_when_ineligible
#   ✓ test_describe_includes_minimum_required
#
# Evaluate Behavior (3):
#   ✓ test_evaluate_allows_when_eligible
#   ✓ test_evaluate_rejects_when_ineligible
#   ✓ test_evaluate_does_not_modify_catch_amount + test_evaluate_preserves_full_amount
#
# Configuration (3):
#   ✓ test_config_activates_norm
#   ✓ test_config_specifies_type
#   ✓ test_config_specifies_min_reserve_kg
#
# Tests Coverage (implied by this file existing and passing)
#
# Additional edge cases and thoroughness (8):
#   ✓ test_per_agent_eligibility_independent
#   ✓ test_per_agent_evaluate_independent
#   ✓ test_very_high_reserve
#   ✓ test_very_low_positive_reserve
#   ✓ test_fractional_reserve_at_boundary
#   ✓ test_custom_minimum_eligibility
#   ✓ test_describe_includes_replenish_instruction_when_ineligible
#   ✓ test_describe_eligible_format
#   ✓ test_eligible_returns_norm_decision_allow
#   ✓ test_ineligible_returns_norm_decision_reject
