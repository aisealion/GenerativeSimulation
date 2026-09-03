from engine.norms.context import HarvestContext
from norms.communal_reserve import CommunalReserveNorm


def _context(stock=100.0):
    return HarvestContext.from_state({
        "config": {}, "fluents": [], "runtime": {"stock_kg": stock},
        "agents": {}, "round_number": 1,
    })


def test_deposit_deducted_from_catch():
    """10% deposit should be deducted from the fisher's kept amount."""
    norm = CommunalReserveNorm(key="communal_reserve", params={"deposit_pct": 0.10})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=10.0, proposed_kg=10.0)
    # 10% of 10kg = 1kg deposited, final kept = 9kg
    assert decision.kept_kg == 9.0


def test_deposit_added_to_reserve_balance():
    """Deposit amount should be added to the communal reserve balance."""
    context = _context()
    norm = CommunalReserveNorm(key="communal_reserve", params={"deposit_pct": 0.10})

    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)

    balance = context.norm_state("communal_reserve")["balance_kg"]
    assert balance == 1.0  # 10% of 10kg


def test_multiple_deposits_accumulate():
    """Multiple fishers' deposits should accumulate in the reserve."""
    context = _context()
    norm = CommunalReserveNorm(key="communal_reserve", params={"deposit_pct": 0.10})

    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)  # 1kg
    norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)  # 2kg
    norm.evaluate(context, "agent_2", raw_kg=5.0, proposed_kg=5.0)    # 0.5kg

    balance = context.norm_state("communal_reserve")["balance_kg"]
    assert balance == 3.5  # 1 + 2 + 0.5


def test_deposit_tracked_per_agent():
    """Each agent's deposit should be tracked individually."""
    context = _context()
    norm = CommunalReserveNorm(key="communal_reserve", params={"deposit_pct": 0.10})

    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    norm.evaluate(context, "agent_1", raw_kg=20.0, proposed_kg=20.0)

    deposits = context.norm_state("communal_reserve")["deposits"]
    assert deposits["agent_0"] == 1.0
    assert deposits["agent_1"] == 2.0


def test_deposit_note_includes_amount():
    """The decision note should mention the deposit amount."""
    norm = CommunalReserveNorm(key="communal_reserve", params={"deposit_pct": 0.10})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=10.0, proposed_kg=10.0)

    assert "1.0kg" in decision.note
    assert "10%" in decision.note


def test_describe_shows_deposit_requirement():
    """describe() should inform agents about the deposit requirement."""
    norm = CommunalReserveNorm(key="communal_reserve", params={"deposit_pct": 0.10})
    description = norm.describe(_context(), "agent_0")

    assert "10%" in description
    assert "communal reserve" in description.lower()


def test_describe_shows_current_balance():
    """describe() should show the current reserve balance."""
    context = _context()
    norm = CommunalReserveNorm(key="communal_reserve", params={"deposit_pct": 0.10})

    # First, make a deposit
    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)

    description = norm.describe(context, "agent_1")
    assert "1kg" in description or "1.0kg" in description


def test_custom_deposit_percentage():
    """Test with a custom deposit percentage."""
    norm = CommunalReserveNorm(key="communal_reserve", params={"deposit_pct": 0.20})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=10.0, proposed_kg=10.0)
    # 20% of 10kg = 2kg deposited, final kept = 8kg
    assert decision.kept_kg == 8.0


def test_deposit_with_zero_catch():
    """With zero catch, deposit should be zero."""
    norm = CommunalReserveNorm(key="communal_reserve", params={"deposit_pct": 0.10})
    decision = norm.evaluate(_context(), "agent_0", raw_kg=0.0, proposed_kg=0.0)
    assert decision.kept_kg == 0.0


def test_lake_replenishment_when_stock_below_threshold():
    """Reserve should replenish lake when stock is below threshold."""
    context = _context(stock=50.0)  # Below 100kg threshold
    norm = CommunalReserveNorm(
        key="communal_reserve",
        params={"deposit_pct": 0.10, "replenish_threshold_kg": 100}
    )

    # Make a deposit to build up reserve
    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    assert context.norm_state("communal_reserve")["balance_kg"] == 1.0

    # Simulate round end with low stock
    round_results = {"agent_0": {"effort": 1.0, "harvested_kg": 9.0, "participated": True, "note": None}}
    norm.on_round_end(context, round_results)

    # Reserve should be emptied (used for replenishment)
    assert context.norm_state("communal_reserve")["balance_kg"] == 0.0
    assert context.norm_state("communal_reserve")["last_replenishment_kg"] == 1.0


def test_no_replenishment_when_stock_above_threshold():
    """Reserve should NOT replenish lake when stock is above threshold."""
    context = _context(stock=150.0)  # Above 100kg threshold
    norm = CommunalReserveNorm(
        key="communal_reserve",
        params={"deposit_pct": 0.10, "replenish_threshold_kg": 100}
    )

    # Make a deposit to build up reserve
    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    assert context.norm_state("communal_reserve")["balance_kg"] == 1.0

    # Simulate round end with high stock
    round_results = {"agent_0": {"effort": 1.0, "harvested_kg": 9.0, "participated": True, "note": None}}
    norm.on_round_end(context, round_results)

    # Reserve should still have the deposit
    assert context.norm_state("communal_reserve")["balance_kg"] == 1.0


def test_replenishment_only_happens_with_balance():
    """Replenishment should only happen if there's something in the reserve."""
    context = _context(stock=50.0)  # Below threshold
    norm = CommunalReserveNorm(
        key="communal_reserve",
        params={"deposit_pct": 0.10, "replenish_threshold_kg": 100}
    )

    # No deposits made, reserve is empty (access through norm to initialize)
    balance = norm._reserve_state(context)["balance_kg"]
    assert balance == 0.0

    # Simulate round end
    round_results = {}
    norm.on_round_end(context, round_results)

    # Should still be empty, no errors
    balance = norm._reserve_state(context)["balance_kg"]
    assert balance == 0.0


def test_deposits_cleared_after_round_end():
    """Deposit tracking should be cleared and moved to deposits_this_round after round end."""
    context = _context()
    norm = CommunalReserveNorm(key="communal_reserve", params={"deposit_pct": 0.10})

    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)
    assert "agent_0" in context.norm_state("communal_reserve")["deposits"]

    round_results = {"agent_0": {"effort": 1.0, "harvested_kg": 9.0, "participated": True, "note": None}}
    norm.on_round_end(context, round_results)

    # deposits should be cleared, deposits_this_round should have the data
    assert "deposits_this_round" in context.norm_state("communal_reserve")
    assert context.norm_state("communal_reserve")["deposits_this_round"]["agent_0"] == 1.0


def test_starting_balance_respected():
    """Starting balance parameter should be used for initial reserve balance."""
    context = _context()
    norm = CommunalReserveNorm(
        key="communal_reserve",
        params={"deposit_pct": 0.10, "starting_balance_kg": 50.0}
    )

    # Access balance through norm to initialize starting balance
    balance = norm._reserve_state(context)["balance_kg"]
    assert balance == 50.0


def test_deposit_accumulates_with_starting_balance():
    """New deposits should add to starting balance."""
    context = _context()
    norm = CommunalReserveNorm(
        key="communal_reserve",
        params={"deposit_pct": 0.10, "starting_balance_kg": 50.0}
    )

    norm.evaluate(context, "agent_0", raw_kg=10.0, proposed_kg=10.0)

    balance = context.norm_state("communal_reserve")["balance_kg"]
    assert balance == 51.0  # 50 starting + 1 deposit
