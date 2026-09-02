from engine.norms.context import HarvestContext
from norms.personal_reserve import PersonalReserveNorm


def _context(runtime=None):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": runtime or {"stock_kg": 100.0},
        "agents": {}, "round_number": 1,
    })


def test_eligible_when_reserve_at_minimum():
    """Agent with exactly 5kg reserve should be eligible."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 5.0}})
    assert norm.is_eligible(context, "agent_0") is True


def test_eligible_when_reserve_above_minimum():
    """Agent with more than 5kg reserve should be eligible."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 10.0}})
    assert norm.is_eligible(context, "agent_0") is True


def test_ineligible_when_reserve_below_minimum():
    """Agent with less than 5kg reserve should be ineligible."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 4.0}})
    assert norm.is_eligible(context, "agent_0") is False


def test_ineligible_when_reserve_zero():
    """Agent with 0kg reserve should be ineligible."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 0.0}})
    assert norm.is_eligible(context, "agent_0") is False


def test_ineligible_when_reserve_negative():
    """Agent with negative reserve (dead agent case) should be ineligible."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": -1.0}})
    assert norm.is_eligible(context, "agent_0") is False


def test_ineligible_when_no_payoff_entry():
    """Agent with no payoff entry (new agent) should be ineligible (0 < 5)."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {}})
    assert norm.is_eligible(context, "agent_0") is False


def test_default_minimum_is_5kg():
    """If min_reserve_kg not specified, default should be 5.0."""
    norm = PersonalReserveNorm(key="personal_reserve", params={})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 4.9}})
    assert norm.is_eligible(context, "agent_0") is False

    context2 = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 5.0}})
    assert norm.is_eligible(context2, "agent_0") is True


def test_custom_minimum():
    """Should respect custom min_reserve_kg parameter."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 10.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 9.0}})
    assert norm.is_eligible(context, "agent_0") is False

    context2 = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 10.0}})
    assert norm.is_eligible(context2, "agent_0") is True


def test_describe_shows_status_when_eligible():
    """describe() should show reserve status when agent is eligible."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 8.5}})
    description = norm.describe(context, "agent_0")
    assert "8.5kg" in description
    assert "5kg" in description
    assert "below" not in description.lower()


def test_describe_shows_warning_when_ineligible():
    """describe() should show warning when agent is ineligible."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 3.0}})
    description = norm.describe(context, "agent_0")
    assert "3.0kg" in description
    assert "below" in description.lower()
    assert "2.0kg" in description  # shortfall amount
    assert "replenish" in description.lower()


def test_evaluate_allows_when_eligible():
    """evaluate() should allow catch when agent is eligible."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 10.0}})
    decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
    assert decision.kept_kg == 15.0
    assert decision.violated is False
    assert decision.sanction is None


def test_evaluate_rejects_when_ineligible():
    """evaluate() should reject when agent is ineligible (safety check)."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={"stock_kg": 100.0, "payoff": {"agent_0": 2.0}})
    decision = norm.evaluate(context, "agent_0", raw_kg=15.0, proposed_kg=15.0)
    assert decision.kept_kg == 0.0
    assert decision.violated is True
    assert "below" in (decision.note or "").lower()
    assert "2.0kg" in (decision.note or "")


def test_per_agent_tracking():
    """Different agents should have independent eligibility based on their own reserves."""
    norm = PersonalReserveNorm(key="personal_reserve", params={"min_reserve_kg": 5.0})
    context = _context(runtime={
        "stock_kg": 100.0,
        "payoff": {
            "agent_0": 10.0,  # eligible
            "agent_1": 3.0,   # ineligible
            "agent_2": 5.0,   # eligible (at minimum)
        }
    })

    assert norm.is_eligible(context, "agent_0") is True
    assert norm.is_eligible(context, "agent_1") is False
    assert norm.is_eligible(context, "agent_2") is True
