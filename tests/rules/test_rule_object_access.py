from engine.institution.context import ActionContext
from engine.institution.rules import Rule

# Proves the actual capability the "reserve deposits whatever a cap
# trimmed off" pattern (actions/rules/README.md's worked example) depends
# on: a Rule subclass's ctx.objects is a real, usable ObjectRuntime, not
# just something present on ActionContext and never touched.

POOL_TYPE = {
    "type_name": "_test_reserve_pool",
    "fields": {"balance_kg": {"type": "number", "default": 0.0}},
    "operations": ["deposit", "withdraw", "read"],
    "permissions": {"WRITE": {"who": "ALL"}, "READ": {"who": "ALL"}},
    "visibility": {"balance_kg": {"who": "ALL"}},
}


class _DepositsOverflow(Rule):
    """A minimal reserve-shaped rule: whatever a previous rule in the
    chain already trimmed off gets deposited into a communal pool — the
    exact ordering-dependent pattern actions/rules/README.md's worked
    example describes. `params["raw_kg"]` stands in for what a real rule
    would re-derive from a field no rule touches (harvest's own "effort",
    say) — this test is about object access, not that re-derivation
    technique, which the harvest baseline test already covers."""

    type_name = "_deposits_overflow_for_test"

    def after_agent(self, ctx, agent_id, record_entry):
        overflow = self.params["raw_kg"] - record_entry["harvested_kg"]
        if overflow > 0:
            ctx.objects.deposit(
                "reserve", "balance_kg", overflow, by_agent_id=agent_id,
                narration=f"{agent_id} deposited {overflow:.1f}kg into the reserve.",
            )
        return None


def _state():
    return {
        "config": {"rules": {"harvest": []}},
        "fluents": [],
        "runtime": {"stock_kg": 300.0, "rounds": []},
        "agents": {},
        "object_types": {"_test_reserve_pool": POOL_TYPE},
        "objects": [{"id": "reserve", "type": "_test_reserve_pool"}],
        "round_number": 1,
    }


def _ctx(state):
    return ActionContext.build({"name": "harvest"}, state, state["round_number"])


def test_a_rule_can_deposit_into_an_institutional_object():
    state = _state()
    ctx = _ctx(state)
    rule = _DepositsOverflow(key="_deposits_overflow_for_test", params={"raw_kg": 20.0})

    # Simulates being chained right after a cap-shaped rule that already
    # trimmed 20kg down to 12kg.
    record_entry = {"harvested_kg": 12.0}
    rule.after_agent(ctx, "agent_0", record_entry)

    assert record_entry["harvested_kg"] == 12.0
    assert ctx.objects.read("reserve", "balance_kg") == 8.0
    assert any(e["event_type"] == "object_mutated" for e in state["events"])


def test_no_overflow_means_no_deposit():
    state = _state()
    ctx = _ctx(state)
    rule = _DepositsOverflow(key="_deposits_overflow_for_test", params={"raw_kg": 12.0})

    record_entry = {"harvested_kg": 12.0}
    rule.after_agent(ctx, "agent_0", record_entry)

    assert ctx.objects.read("reserve", "balance_kg") == 0.0
    assert state["events"] == []
