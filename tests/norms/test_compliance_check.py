from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.compliance_check import ComplianceCheckNorm


def _context(stock=100.0):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": stock},
        "agents": {}, "round_number": 1,
    })


def test_agent_eligible_by_default():
    """Agent should be eligible when they have no compliance history."""
    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )
    assert norm.is_eligible(_context(), "agent_0") is True


def test_no_quota_reduction_when_compliant():
    """Agent with normal compliance should get full catch limit."""
    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )
    decision = norm.evaluate(_context(stock=100.0), "agent_0", raw_kg=10.0, proposed_kg=10.0)
    assert decision.kept_kg == 10.0
    assert decision.violated is False


def test_deposit_tracked_as_compliance():
    """Agent who made a deposit should be marked compliant."""
    context = _context()
    # Simulate deposit tracking from communal_reserve
    context.norm_state("communal_reserve")["deposits_this_round"] = {"agent_0": 1.0}

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    decision = NormDecision(kept_kg=9.0, sanction=None, violated=False)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=9.0)

    state = context.norm_state("compliance_check")["agent_0"]
    assert state["compliant_last_round"] is True


def test_no_deposit_tracked_as_non_compliant():
    """Agent who didn't make a deposit should be marked non-compliant."""
    context = _context()
    # Empty deposits - agent_0 didn't deposit
    context.norm_state("communal_reserve")["deposits_this_round"] = {}

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    decision = NormDecision(kept_kg=10.0, sanction=None, violated=False)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=10.0)

    state = context.norm_state("compliance_check")["agent_0"]
    assert state["compliant_last_round"] is False


def test_reduced_quota_applied_after_non_compliance():
    """Agent should get reduced quota (6%) after missing deposit."""
    context = _context(stock=100.0)
    # Mark agent as having missed deposit last round
    context.norm_state("compliance_check")["agent_0"] = {
        "compliant_last_round": False,
        "using_reduced_quota": True
    }

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    # Try to catch 12% (12kg) but should be limited to 6% (6kg)
    decision = norm.evaluate(context, "agent_0", raw_kg=12.0, proposed_kg=12.0)
    assert decision.kept_kg == 6.0  # 6% of 100kg
    assert decision.violated is True
    assert decision.sanction == "missed_deposit"


def test_reduced_quota_not_exceeded():
    """Agent under reduced quota should be allowed up to 6%."""
    context = _context(stock=100.0)
    context.norm_state("compliance_check")["agent_0"] = {
        "compliant_last_round": False,
        "using_reduced_quota": True
    }

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    # Catching exactly 6% should be allowed
    decision = norm.evaluate(context, "agent_0", raw_kg=6.0, proposed_kg=6.0)
    assert decision.kept_kg == 6.0
    assert decision.violated is False


def test_reduced_quota_lifted_after_compliance():
    """Reduced quota should be lifted after agent makes a deposit."""
    context = _context(stock=100.0)
    # Agent was on reduced quota
    context.norm_state("compliance_check")["agent_0"] = {
        "compliant_last_round": False,
        "using_reduced_quota": True
    }
    # But made a deposit this round
    context.norm_state("communal_reserve")["deposits_this_round"] = {"agent_0": 1.0}

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    decision = NormDecision(kept_kg=6.0, sanction="missed_deposit", violated=True)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=6.0)

    # Should no longer be using reduced quota
    state = context.norm_state("compliance_check")["agent_0"]
    assert state["using_reduced_quota"] is False


def test_describe_shows_reduced_quota_warning():
    """describe() should warn agent when they have reduced quota."""
    context = _context()
    context.norm_state("compliance_check")["agent_0"] = {
        "compliant_last_round": False,
        "using_reduced_quota": True
    }

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    description = norm.describe(context, "agent_0")
    assert "6%" in description
    assert "reduced" in description.lower()


def test_describe_none_when_normal_quota():
    """describe() should return None when agent has normal quota."""
    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    assert norm.describe(_context(), "agent_0") is None


def test_round_end_marks_non_compliant_for_reduced_quota():
    """on_round_end should mark non-compliant agents for reduced quota next round."""
    context = _context()
    # agent_0 didn't deposit
    context.norm_state("communal_reserve")["deposits_this_round"] = {"agent_1": 1.0}  # Only agent_1 deposited

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    round_results = {
        "agent_0": {"effort": 1.0, "harvested_kg": 10.0, "participated": True, "note": None},
        "agent_1": {"effort": 1.0, "harvested_kg": 9.0, "participated": True, "note": None}
    }
    norm.on_round_end(context, round_results)

    # agent_0 should be marked for reduced quota
    assert context.norm_state("compliance_check")["agent_0"]["using_reduced_quota"] is True
    # agent_1 should not
    assert context.norm_state("compliance_check")["agent_1"]["using_reduced_quota"] is False


def test_custom_reduced_percentage():
    """Test with a custom reduced percentage."""
    context = _context(stock=100.0)
    context.norm_state("compliance_check")["agent_0"] = {
        "compliant_last_round": False,
        "using_reduced_quota": True
    }

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.08, "normal_pct": 0.12}
    )

    # Should be limited to 8% (8kg) instead of 6%
    decision = norm.evaluate(context, "agent_0", raw_kg=12.0, proposed_kg=12.0)
    assert decision.kept_kg == 8.0


def test_custom_sanction_name():
    """Test with a custom sanction name."""
    context = _context(stock=100.0)
    context.norm_state("compliance_check")["agent_0"] = {
        "compliant_last_round": False,
        "using_reduced_quota": True
    }

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12, "trigger_sanction": "no_deposit"}
    )

    decision = norm.evaluate(context, "agent_0", raw_kg=12.0, proposed_kg=12.0)
    assert decision.sanction == "no_deposit"


def test_compliance_per_agent():
    """Compliance should be tracked separately per agent."""
    context = _context()
    context.norm_state("communal_reserve")["deposits_this_round"] = {"agent_0": 1.0}  # Only agent_0 deposited

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    round_results = {
        "agent_0": {"effort": 1.0, "harvested_kg": 9.0, "participated": True, "note": None},
        "agent_1": {"effort": 1.0, "harvested_kg": 10.0, "participated": True, "note": None}
    }
    norm.on_round_end(context, round_results)

    # agent_0 was compliant
    assert context.norm_state("compliance_check")["agent_0"]["compliant_last_round"] is True
    assert context.norm_state("compliance_check")["agent_0"]["using_reduced_quota"] is False

    # agent_1 was not compliant
    assert context.norm_state("compliance_check")["agent_1"]["compliant_last_round"] is False
    assert context.norm_state("compliance_check")["agent_1"]["using_reduced_quota"] is True


def test_zero_deposit_counts_as_non_compliant():
    """Zero deposit amount should count as non-compliant."""
    context = _context()
    # agent_0 has 0 deposit (either in dict with 0 value or missing)
    context.norm_state("communal_reserve")["deposits_this_round"] = {"agent_0": 0.0}

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    decision = NormDecision(kept_kg=0.0, sanction=None, violated=False)
    norm.on_agent_settled(context, "agent_0", decision, harvested_kg=0.0)

    state = context.norm_state("compliance_check")["agent_0"]
    assert state["compliant_last_round"] is False


def test_describe_warns_about_reduced_quota_next_round():
    """describe() should inform agent they missed deposit and have reduced quota."""
    context = _context()
    context.norm_state("compliance_check")["agent_0"] = {
        "compliant_last_round": False,
        "using_reduced_quota": True
    }

    norm = ComplianceCheckNorm(
        key="compliance_check",
        params={"deposit_norm_id": "communal_reserve", "reduced_pct": 0.06, "normal_pct": 0.12}
    )

    description = norm.describe(context, "agent_0")
    assert "missed" in description.lower() or "failed" in description.lower()
    assert "deposit" in description.lower()
