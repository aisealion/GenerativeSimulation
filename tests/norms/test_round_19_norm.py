from engine.norms.base import NormDecision
from engine.norms.context import HarvestContext
from norms.round_19_norm import Round19Norm


def _context(stock=100.0):
    return HarvestContext.from_state({
        "config": {},
        "fluents": [],
        "runtime": {"stock_kg": stock},
        "agents": {},
        "round_number": 1,
    })


def test_trip_limit_exceeded():
    ctx = _context()
    norm = Round19Norm(key="r19", params={})
    decision = norm.evaluate(ctx, "agent_0", raw_kg=2.5, proposed_kg=2.5)
    assert decision.kept_kg == 0.0
    assert decision.sanction == "trip_limit_exceeded"
    assert "trip limit exceeded" in (decision.note or "")


def test_personal_keep_under_one():
    ctx = _context()
    norm = Round19Norm(key="r19", params={})
    decision = norm.evaluate(ctx, "agent_0", raw_kg=0.8, proposed_kg=0.8)
    assert decision.kept_kg == 0.8
    assert decision.sanction is None


def test_monthly_cap_enforcement():
    # Stock start 100 kg → month cap = min(30%*100, 3) = 3 kg.
    ctx = _context()
    norm = Round19Norm(key="r19", params={})
    # First two agents each contribute 1 kg community (catch 2 kg total).
    d1 = norm.evaluate(ctx, "a1", raw_kg=2.0, proposed_kg=2.0)
    d2 = norm.evaluate(ctx, "a2", raw_kg=2.0, proposed_kg=2.0)
    assert d1.sanction is None and d2.sanction is None
    # Third agent would push community total to 3 kg (still ok).
    d3 = norm.evaluate(ctx, "a3", raw_kg=2.0, proposed_kg=2.0)
    assert d3.sanction is None
    # Fourth agent exceeds the 3 kg cap.
    d4 = norm.evaluate(ctx, "a4", raw_kg=2.0, proposed_kg=2.0)
    assert d4.sanction == "monthly_cap_exceeded"
    assert d4.kept_kg == 1.0  # personal keep still allowed
    assert "monthly cap exceeded" in (d4.note or "")
