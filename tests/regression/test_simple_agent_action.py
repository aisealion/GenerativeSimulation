from engine.action_base import SimpleAgentAction
from roles.grants import RoleGrant, InstitutionalFact
from roles.roles import current_holder, visible_facts


def _state(agents, dead_agents=None):
    return {
        "config": {},
        "fluents": [],
        "runtime": {"stock_kg": 300.0, "rounds": [], "dead_agents": dead_agents or []},
        "agents": agents,
        "round_number": 1,
    }


AGENTS = {
    "agent_0": {"name": "Kai", "personality_traits": ""},
    "agent_1": {"name": "Mara", "personality_traits": ""},
    "agent_2": {"name": "Toa", "personality_traits": ""},
}

TWO_AGENTS = {aid: a for aid, a in AGENTS.items() if aid != "agent_2"}


class _EchoAction(SimpleAgentAction):
    """Minimal fixture — one call per participant, echoing back a
    caller-supplied response. Never touches harvest/propose/vote."""

    name = "_echo_for_test"

    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def build_fields(self, state, setup_ctx, agent_id):
        return {}

    def call_agent(self, agent_id, round_number, fields):
        self.calls.append(agent_id)
        return self._responses[agent_id]

    def record_result(self, state, setup_ctx, agent_id, response):
        return {"echoed": response["value"]}


def test_default_participants_and_after_participants_aggregation():
    """Default participants() excludes dead agents; after_participants()'s
    extra fields land at the round_record's top level alongside the
    per-agent dict."""
    class _WithSummary(_EchoAction):
        def after_participants(self, state, setup_ctx, agent_records):
            return {"summary": len(agent_records)}

    action = _WithSummary({"agent_0": {"value": 1}, "agent_1": {"value": 2}})
    state = _state(AGENTS, dead_agents=["agent_2"])

    record = action.run(state)

    assert set(record["agents"]) == {"agent_0", "agent_1"}
    assert record["agents"]["agent_0"] == {"echoed": 1}
    assert record["summary"] == 2
    assert record["round"] == 1
    assert record["action"] == "_echo_for_test"
    assert state["runtime"]["rounds"] == [record]


def test_eligibility_skip_never_calls_the_agent():
    """A rejected agent's call_agent() is never invoked; its round_record
    entry is exactly whatever ineligible_result() returns."""

    class _WithEligibility(_EchoAction):
        def is_eligible(self, state, setup_ctx, agent_id):
            return agent_id != "agent_1"

        def ineligible_result(self, state, setup_ctx, agent_id):
            return {"echoed": None, "skipped": True}

    action = _WithEligibility({"agent_0": {"value": 1}, "agent_2": {"value": 3}})
    state = _state(AGENTS)

    record = action.run(state)

    assert "agent_1" not in action.calls
    assert record["agents"]["agent_1"] == {"echoed": None, "skipped": True}
    assert record["agents"]["agent_0"] == {"echoed": 1}


def test_exclusive_role_rotation_closes_the_previous_holder():
    """The documented assign_role() footgun (a rotating role's outgoing
    holder never actually closing, because a default args=[agent_id]
    differs between holders) must be structurally unreachable via
    RoleGrant(exclusive=True) — this is the proof."""

    class _RoleGranting(_EchoAction):
        def role_grant(self, state, setup_ctx, agent_id, response):
            if not response.get("claim"):
                return None
            return RoleGrant(role_name="_recorder_for_test", exclusive=True,
                              narration=f"{agent_id} is now recorder.")

    fluents = []

    round1 = _RoleGranting({"agent_0": {"value": 0, "claim": True}, "agent_1": {"value": 0}})
    state1 = _state(TWO_AGENTS)
    state1["fluents"] = fluents
    round1.run(state1)

    round2_state = _state(TWO_AGENTS)
    round2_state["fluents"] = fluents
    round2_state["round_number"] = 2
    round2 = _RoleGranting({"agent_0": {"value": 0}, "agent_1": {"value": 0, "claim": True}})
    round2.run(round2_state)

    agent_0_record = next(r for r in fluents if r["holder"] == "agent_0")
    agent_1_record = next(r for r in fluents if r["holder"] == "agent_1")
    assert agent_0_record["terminated_round"] == 2
    assert agent_1_record["terminated_round"] is None
    assert current_holder(fluents, "_recorder_for_test", 2) == "agent_1"


def test_institutional_fact_is_publicly_visible_to_a_different_agent():
    class _FactRecording(_EchoAction):
        def institutional_fact(self, state, setup_ctx, agent_id, response):
            if "note" not in response:
                return None
            return InstitutionalFact(
                fluent_name="_ledger_for_test", holder="community",
                narration=response["note"], visibility="public",
            )

    action = _FactRecording({"agent_0": {"value": 0, "note": "5kg logged"}, "agent_1": {"value": 0}})
    state = _state(TWO_AGENTS)

    action.run(state)

    visible = visible_facts(state["fluents"], "agent_1", 1)
    assert any(f["narration"] == "5kg logged" for f in visible)
