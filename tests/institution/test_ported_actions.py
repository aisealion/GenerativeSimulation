import pytest

import engine.llm_agents as llm_agents_module
import actions.handlers.propose as propose_handler
import actions.handlers.critique as critique_handler
import actions.handlers.vote as vote_handler
import actions.handlers.discuss as discuss_handler
from engine.institution.context import ActionContext
from engine.institution.runtime import ActionRuntime

AGENTS = {
    "agent_0": {"name": "Kai", "personality_traits": ""},
    "agent_1": {"name": "Mara", "personality_traits": ""},
}


def _state_with_harvest(harvest_agents, round_number=1):
    return {
        "config": {},
        "fluents": [],
        "runtime": {
            "stock_kg": 280.0,
            "rounds": [{"round": round_number, "action": "harvest", "agents": harvest_agents}],
        },
        "agents": AGENTS,
        "round_number": round_number,
    }


def _state_with_proposals(proposals, round_number=1):
    return {
        "config": {},
        "fluents": [],
        "runtime": {
            "stock_kg": 300.0,
            "rounds": [{"round": round_number, "action": "propose", "proposals": proposals}],
        },
        "agents": AGENTS,
        "round_number": round_number,
    }


PROPOSALS = {
    "agent_0": {"policy": "cap catches", "operationalization": "15kg per trip", "reasoning": ""},
    "agent_1": {"policy": "share the surplus", "operationalization": "pool it weekly", "reasoning": ""},
}


# ---- propose ----

def test_propose_computes_others_summary_and_records_policy(monkeypatch):
    seen_fields = {}

    def _fake_call(agent_id, round_number, action_name, **fields):
        seen_fields[agent_id] = fields
        return {"policy": f"policy from {agent_id}", "operationalization": "...", "reasoning": ""}

    monkeypatch.setattr(llm_agents_module, "call_fisher_agent", _fake_call)
    state = _state_with_harvest({
        "agent_0": {"harvested_kg": 10.0}, "agent_1": {"harvested_kg": 4.0},
    })
    ctx = ActionContext.build({"name": "propose"}, state, state["round_number"])

    record = propose_handler.run(ctx)

    assert record["proposals"]["agent_0"]["policy"] == "policy from agent_0"
    assert "Mara brought in 4kg" in seen_fields["agent_0"]["others_summary"]
    assert seen_fields["agent_0"]["your_catch_kg"] == 10.0

    memory = propose_handler.memory_writes(state, record)
    assert memory[0]["event_type"] == "proposal_made"
    assert memory[0]["agent_id"] == "agent_0"


# ---- critique ----

def test_critique_sufficient_on_first_pass_leaves_proposal_unchanged(monkeypatch):
    fisher_calls = []
    monkeypatch.setattr(critique_handler, "call_critique_agent", lambda **k: {"status": "SUFFICIENT"})
    monkeypatch.setattr(critique_handler, "call_fisher_agent", lambda *a, **k: fisher_calls.append(a) or {})

    state = _state_with_proposals(PROPOSALS)
    ctx = ActionContext.build({"name": "critique"}, state, state["round_number"])

    record = critique_handler.run(ctx)

    assert fisher_calls == []
    assert record["proposals"] == PROPOSALS
    assert record["dialogues"]["agent_0"] == []


def test_critique_one_question_then_sufficient_applies_finalized_revision(monkeypatch):
    def _fake_critique(policy, operationalization, history, round_number=None, proposer_id=None):
        if proposer_id == "agent_0" and not history:
            return {"status": "QUESTION", "question": "Who holds the deposit?"}
        return {"status": "SUFFICIENT"}

    finalize_calls = []

    def _fake_fisher(agent_id, round_number, action_name, **fields):
        if action_name == "critique_response":
            return {
                "answer": "The community holds it.",
                "revised_policy": "cap catches (draft)",
                "revised_operationalization": "15kg per trip (draft)",
                "reasoning": "clarifying",
            }
        finalize_calls.append(agent_id)
        return {"policy": "cap catches, community holds any deposit",
                "operationalization": "15kg per trip; excess deposit held by the community",
                "reasoning": "final"}

    monkeypatch.setattr(critique_handler, "call_critique_agent", _fake_critique)
    monkeypatch.setattr(critique_handler, "call_fisher_agent", _fake_fisher)

    state = _state_with_proposals(PROPOSALS)
    ctx = ActionContext.build({"name": "critique"}, state, state["round_number"])
    record = critique_handler.run(ctx)

    assert finalize_calls == ["agent_0"]
    assert record["proposals"]["agent_0"]["policy"] == "cap catches, community holds any deposit"
    assert record["proposals"]["agent_1"] == PROPOSALS["agent_1"]

    memory = critique_handler.memory_writes(state, record)
    assert [m["agent_id"] for m in memory] == ["agent_0"]


def test_critique_loop_is_bounded(monkeypatch):
    call_count = {"n": 0}

    def _always_asks(policy, operationalization, history, round_number=None, proposer_id=None):
        call_count["n"] += 1
        return {"status": "QUESTION", "question": f"q{len(history) + 1}"}

    def _fake_fisher(agent_id, round_number, action_name, **fields):
        if action_name == "critique_finalize":
            return {"policy": "final policy", "operationalization": "final op"}
        return {"answer": "sure", "revised_policy": "cap catches", "revised_operationalization": "15kg"}

    monkeypatch.setattr(critique_handler, "call_critique_agent", _always_asks)
    monkeypatch.setattr(critique_handler, "call_fisher_agent", _fake_fisher)

    state = _state_with_proposals({"agent_0": PROPOSALS["agent_0"]})
    state["agents"] = {"agent_0": AGENTS["agent_0"]}
    ctx = ActionContext.build({"name": "critique"}, state, state["round_number"])
    record = critique_handler.run(ctx)

    assert call_count["n"] == critique_handler.MAX_CRITIQUE_EXCHANGES
    assert record["proposals"]["agent_0"]["policy"] == "final policy"


# ---- vote ----

def test_vote_prefers_critique_proposals_when_present():
    state = _state_with_proposals(PROPOSALS)
    refined = {"agent_0": {"policy": "cap catches, refined", "operationalization": "..."},
               "agent_1": PROPOSALS["agent_1"]}
    state["runtime"]["rounds"].append({"round": 1, "action": "critique", "proposals": refined, "dialogues": {}})

    proposals = vote_handler.proposals_for_round(state)
    assert dict(proposals)["agent_0"]["policy"] == "cap catches, refined"


def test_vote_falls_back_to_propose_when_no_critique_record():
    state = _state_with_proposals(PROPOSALS)
    proposals = vote_handler.proposals_for_round(state)
    assert dict(proposals) == PROPOSALS


def test_vote_tallies_and_sets_adopted_norm(monkeypatch):
    votes_by_agent = {"agent_0": "2", "agent_1": "2"}
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent",
                         lambda agent_id, round_number, action_name, **f: {"vote": votes_by_agent[agent_id]})

    state = _state_with_proposals(PROPOSALS)
    ctx = ActionContext.build({"name": "vote"}, state, state["round_number"])
    record = vote_handler.run(ctx)

    assert record["tally"] == {1: 0, 2: 2}
    assert record["winner_index"] == 2
    assert record["winning_proposer"] == "agent_1"
    assert state["adopted_norm"]["policy"] == "share the surplus"

    memory = vote_handler.memory_writes(state, record)
    assert memory[0]["event_type"] == "vote_outcome"


def test_discuss_still_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        discuss_handler.run(None)


# ---- generic runtime dispatch, via ActionRuntime.run_action ----

def test_action_runtime_dispatches_to_a_handler_module_and_finalizes_the_record(monkeypatch):
    monkeypatch.setattr(llm_agents_module, "call_fisher_agent",
                         lambda agent_id, round_number, action_name, **f: {"vote": "1"})

    state = _state_with_proposals(PROPOSALS)
    spec = {"name": "vote", "execution": {"handler": "vote"}}

    record = ActionRuntime.run_action(spec, state, state["round_number"])

    assert record["round"] == 1
    assert record["action"] == "vote"
    assert state["runtime"]["rounds"][-1] is record
