from engine.norms.base import Norm, NormDecision
from engine.norms.context import HarvestContext

# Proves the actual capability the "reserve deposits whatever a cap
# trimmed off" pattern (norms/README.md's worked example) depends on: a
# Norm subclass's context.objects is a real, usable ObjectRuntime, not
# just something present on the dataclass and never touched.

POOL_TYPE = {
    "type_name": "_test_reserve_pool",
    "fields": {"balance_kg": {"type": "number", "default": 0.0}},
    "operations": ["deposit", "withdraw", "read"],
    "permissions": {"WRITE": {"who": "ALL"}, "READ": {"who": "ALL"}},
    "visibility": {"balance_kg": {"who": "ALL"}},
}


class _DepositsOverflow(Norm):
    """A minimal reserve-shaped norm: whatever a previous norm in the
    chain already trimmed off (raw_kg - proposed_kg) gets deposited into a
    communal pool — the exact ordering-dependent pattern norms/README.md's
    worked example describes."""

    type_name = "_deposits_overflow_for_test"

    def evaluate(self, context, agent_id, raw_kg, proposed_kg):
        overflow = raw_kg - proposed_kg
        if overflow > 0:
            context.objects.deposit(
                "reserve", "balance_kg", overflow, by_agent_id=agent_id,
                narration=f"{agent_id} deposited {overflow:.1f}kg into the reserve.",
            )
        return NormDecision.allow(proposed_kg)


def _state():
    return {
        "config": {"norms": []},
        "fluents": [],
        "runtime": {"stock_kg": 300.0, "rounds": []},
        "agents": {},
        "object_types": {"_test_reserve_pool": POOL_TYPE},
        "objects": [{"id": "reserve", "type": "_test_reserve_pool"}],
        "round_number": 1,
    }


def test_a_norm_can_deposit_into_an_institutional_object():
    state = _state()
    context = HarvestContext.from_state(state)
    norm = _DepositsOverflow(key="_deposits_overflow_for_test", params={})

    # Simulates being chained right after a cap-type norm that already
    # trimmed 20kg down to 12kg — this norm sees both numbers directly,
    # per NormEngine.apply()'s own raw_kg/proposed_kg contract.
    decision = norm.evaluate(context, "agent_0", raw_kg=20.0, proposed_kg=12.0)

    assert decision.kept_kg == 12.0
    assert context.objects.read("reserve", "balance_kg") == 8.0
    assert any(e["event_type"] == "object_mutated" for e in state["events"])


def test_no_overflow_means_no_deposit():
    state = _state()
    context = HarvestContext.from_state(state)
    norm = _DepositsOverflow(key="_deposits_overflow_for_test", params={})

    norm.evaluate(context, "agent_0", raw_kg=12.0, proposed_kg=12.0)

    assert context.objects.read("reserve", "balance_kg") == 0.0
    assert state["events"] == []
