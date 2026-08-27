from engine.norms.context import HarvestContext
from norms.community_cap import CommunityCapNorm


def _context(stock=100.0):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": stock},
        "agents": {}, "round_number": 1,
    })


def test_running_tally_trims_the_agent_who_pushes_over_the_limit():
    norm = CommunityCapNorm(key="cap", params={"cap_kg": 10})
    context = _context()
    d1 = norm.evaluate(context, "agent_0", raw_kg=6.0, proposed_kg=6.0)
    assert d1.kept_kg == 6.0
    d2 = norm.evaluate(context, "agent_1", raw_kg=6.0, proposed_kg=6.0)  # would bring total to 12
    assert d2.kept_kg == 4.0  # only 4kg of allowance left
    assert d2.violated is True
    assert d2.sanction == "over_community_cap"


def test_pct_of_stock_cap():
    norm = CommunityCapNorm(key="cap", params={"cap_pct_of_stock": 0.1})
    context = _context(stock=200.0)
    decision = norm.evaluate(context, "agent_0", raw_kg=50.0, proposed_kg=50.0)
    assert decision.kept_kg == 20.0  # 10% of 200


def test_no_cap_configured_is_a_no_op():
    norm = CommunityCapNorm(key="cap", params={})
    context = _context()
    decision = norm.evaluate(context, "agent_0", raw_kg=999.0, proposed_kg=999.0)
    assert decision.kept_kg == 999.0


def test_scratch_resets_between_separate_context_instances():
    """Two consecutive rounds each get a fresh HarvestContext (per
    phases/harvest.py's run()) — proves the ephemeral-vs-persistent split:
    the running tally must not leak from one round into the next."""
    norm = CommunityCapNorm(key="cap", params={"cap_kg": 10})
    round_one = _context()
    norm.evaluate(round_one, "agent_0", raw_kg=10.0, proposed_kg=10.0)

    round_two = _context()  # a brand new context, as a new round would build
    decision = norm.evaluate(round_two, "agent_1", raw_kg=10.0, proposed_kg=10.0)
    assert decision.kept_kg == 10.0  # full allowance again, not exhausted by round_one


def test_replenish_triggers_exactly_at_threshold_crossing():
    norm = CommunityCapNorm(key="cap", params={"replenish_if_over_pct": 0.5})
    context = _context(stock=100.0)
    norm.on_round_end(context, {"agent_0": {"harvested_kg": 50.0}})  # exactly 50%, not over
    assert context.stock_override_kg is None

    context2 = _context(stock=100.0)
    norm.on_round_end(context2, {"agent_0": {"harvested_kg": 50.01}})  # just over 50%
    assert context2.stock_override_kg == 100.0


def test_no_replenish_rule_configured_never_overrides():
    norm = CommunityCapNorm(key="cap", params={"cap_kg": 10})
    context = _context()
    norm.on_round_end(context, {"agent_0": {"harvested_kg": 999.0}})
    assert context.stock_override_kg is None


def test_describe_reports_remaining_allowance():
    norm = CommunityCapNorm(key="cap", params={"cap_kg": 10})
    context = _context()
    norm.evaluate(context, "agent_0", raw_kg=4.0, proposed_kg=4.0)
    assert norm.describe(context, "agent_0") == "The community has 6kg left of its shared allowance for this round."
