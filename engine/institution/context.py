# ActionContext: the one object every action handler (builtin or custom,
# under actions/handlers/) receives. Generalizes what SimpleAgentAction used
# to give a subclass implicitly (state, participants, a way to call the
# fisher agent, a way to record a role/fact) into an explicit, small
# interface — engine.institution.runtime.ActionRuntime is the only thing
# that constructs one.

from engine.physics import alive_agent_ids
from engine.institution.events import EventEmitter
from engine.institution.objects import ObjectRuntime


class AgentCaller:
    """`ctx.agents` — calls the unmodified engine.llm_agents.call_fisher_agent()
    for this action, so a handler never needs to import or know about
    persona/prompt rendering itself."""

    def __init__(self, action_name, round_number):
        self.action_name = action_name
        self.round_number = round_number

    def call(self, agent_id, **fields):
        from engine.llm_agents import call_fisher_agent
        return call_fisher_agent(agent_id, self.round_number, self.action_name, **fields)


def resolve_participants(spec, state):
    """The participants for this round, per ActionSpec["participation"].
    Default ("all_alive_fishers") is byte-identical to today's
    alive_agent_ids() — every existing action's real behavior."""
    participation = spec.get("participation", {"policy": "all_alive_fishers"})
    policy = participation.get("policy", "all_alive_fishers")
    if policy == "all_alive_fishers":
        return alive_agent_ids(state["agents"], state["runtime"])
    if policy == "role_holders":
        role_name = participation["role"]
        round_number = state["round_number"]
        return [
            record["holder"] for record in state["fluents"]
            if record["fluent"] == role_name
            and record["initiated_round"] <= round_number
            and (record["terminated_round"] is None or record["terminated_round"] > round_number)
        ]
    raise ValueError(f"unknown participation policy {policy!r}")


class ActionContext:
    """`ctx` — spec (this action's own ActionSpec dict), state (the full
    round-state dict: config/fluents/runtime/agents/round_number), the
    resolved participant list, `.agents` (AgentCaller), `.events`
    (EventEmitter — appends a point-in-time occurrence to
    state["events"], never a fact with a duration; see
    engine.institution.events), and `.objects` (ObjectRuntime, built from
    state.get("object_types", {}) — loaded by engine.simulate.load_state()
    — plus state["objects"] (declarations) and state["runtime"]["objects"]
    (mutable field values, kept separate from the declaration exactly as
    runtime["norms"][key] is kept separate from a norm's own config
    entry)."""

    def __init__(self, spec, state, round_number, participants):
        self.spec = spec
        self.state = state
        self.round_number = round_number
        self.participants = participants
        self.agents = AgentCaller(spec["name"], round_number)
        self.events = EventEmitter(
            state.setdefault("events", []), state["fluents"], round_number, participants=participants,
        )
        self.objects = ObjectRuntime(
            state.get("object_types", {}), state.setdefault("objects", []),
            state["runtime"].setdefault("objects", {}),
            state["fluents"], round_number, self.events,
        )

    @classmethod
    def build(cls, spec, state, round_number):
        participants = resolve_participants(spec, state)
        return cls(spec, state, round_number, participants)
