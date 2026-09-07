import actions.critique as critique_module
import actions.vote as vote_module


def _state_with_proposals(proposals, round_number=1):
    return {
        "config": {},
        "fluents": [],
        "runtime": {
            "stock_kg": 300.0,
            "rounds": [
                {"round": round_number, "action": "propose", "proposals": proposals},
            ],
        },
        "agents": {
            "agent_0": {"name": "Kai", "personality_traits": ""},
            "agent_1": {"name": "Mara", "personality_traits": ""},
        },
        "round_number": round_number,
    }


PROPOSALS = {
    "agent_0": {"policy": "cap catches", "operationalization": "15kg per trip", "reasoning": ""},
    "agent_1": {"policy": "share the surplus", "operationalization": "pool it weekly", "reasoning": ""},
}


def test_sufficient_on_first_pass_leaves_proposal_unchanged_and_never_calls_fisher(monkeypatch):
    fisher_calls = []
    monkeypatch.setattr(critique_module, "call_critique_agent", lambda **k: {"status": "SUFFICIENT"})
    monkeypatch.setattr(critique_module, "call_fisher_agent", lambda *a, **k: fisher_calls.append(a) or {})

    state = _state_with_proposals(PROPOSALS)
    record = critique_module.ACTION.run(state)

    assert fisher_calls == []
    assert record["proposals"] == PROPOSALS
    assert record["dialogues"]["agent_0"] == []
    assert record["dialogues"]["agent_1"] == []


def test_one_question_then_sufficient_applies_the_finalized_revision(monkeypatch):
    def _fake_critique(policy, operationalization, history, round_number=None, proposer_id=None):
        # agent_0 gets exactly one question (on its first call, empty
        # history) then SUFFICIENT; agent_1 gets SUFFICIENT immediately —
        # each proposal's own loop is independent, keyed by proposer_id,
        # not a shared call counter.
        if proposer_id == "agent_0" and not history:
            return {"status": "QUESTION", "question": "Who holds the deposit?"}
        return {"status": "SUFFICIENT"}

    finalize_calls = []

    def _fake_fisher(agent_id, round_number, action_name, **fields):
        if action_name == "critique_response":
            assert fields["question"] == "Who holds the deposit?"
            return {
                "answer": "The community holds it.",
                "revised_policy": "cap catches, community holds any deposit (draft)",
                "revised_operationalization": "15kg per trip; excess deposit held by the community (draft)",
                "reasoning": "clarifying",
            }
        assert action_name == "critique_finalize"
        finalize_calls.append((agent_id, fields))
        assert "Who holds the deposit?" in fields["dialogue_summary"]
        return {
            "policy": "cap catches, community holds any deposit",
            "operationalization": "15kg per trip; excess deposit held by the community",
            "reasoning": "final",
        }

    monkeypatch.setattr(critique_module, "call_critique_agent", _fake_critique)
    monkeypatch.setattr(critique_module, "call_fisher_agent", _fake_fisher)

    state = _state_with_proposals(PROPOSALS)
    record = critique_module.ACTION.run(state)

    # Exactly one finalize call, for agent_0 only (agent_1 never had an
    # exchange, so nothing to finalize).
    assert [a for a, _ in finalize_calls] == ["agent_0"]
    assert record["proposals"]["agent_0"]["policy"] == "cap catches, community holds any deposit"
    assert len(record["dialogues"]["agent_0"]) == 1
    assert record["dialogues"]["agent_0"][0]["question"] == "Who holds the deposit?"
    # agent_1 got a real SUFFICIENT on its own first call — independent per proposal.
    assert record["proposals"]["agent_1"] == PROPOSALS["agent_1"]


def test_loop_is_bounded_even_if_critique_never_says_sufficient(monkeypatch):
    call_count = {"n": 0}
    finalize_calls = {"n": 0}

    def _always_asks(policy, operationalization, history, round_number=None, proposer_id=None):
        call_count["n"] += 1
        return {"status": "QUESTION", "question": f"question #{len(history) + 1}"}

    def _fake_fisher(agent_id, round_number, action_name, **fields):
        if action_name == "critique_finalize":
            finalize_calls["n"] += 1
            return {"policy": "cap catches (final)", "operationalization": "15kg per trip (final)"}
        return {
            "answer": "sure",
            "revised_policy": "cap catches",
            "revised_operationalization": "15kg per trip",
        }

    monkeypatch.setattr(critique_module, "call_critique_agent", _always_asks)
    monkeypatch.setattr(critique_module, "call_fisher_agent", _fake_fisher)

    state = _state_with_proposals({"agent_0": PROPOSALS["agent_0"]})
    # Only one alive agent for this test — trim the roster so we're only
    # counting agent_0's own exchange budget.
    state["agents"] = {"agent_0": {"name": "Kai", "personality_traits": ""}}
    record = critique_module.ACTION.run(state)

    assert call_count["n"] == critique_module.MAX_CRITIQUE_EXCHANGES
    assert len(record["dialogues"]["agent_0"]) == critique_module.MAX_CRITIQUE_EXCHANGES
    # Budget exhaustion still counts as "at least one exchange happened" —
    # the finalize step runs exactly once at the end, not once per exchange.
    assert finalize_calls["n"] == 1
    assert record["proposals"]["agent_0"]["policy"] == "cap catches (final)"


def test_vote_prefers_critique_proposals_when_present_for_this_round():
    state = _state_with_proposals(PROPOSALS)
    refined = {
        "agent_0": {"policy": "cap catches, refined", "operationalization": "..."},
        "agent_1": PROPOSALS["agent_1"],
    }
    state["runtime"]["rounds"].append(
        {"round": 1, "action": "critique", "proposals": refined, "dialogues": {}}
    )

    proposals = vote_module.ACTION._proposals(state)

    assert dict(proposals)["agent_0"]["policy"] == "cap catches, refined"


def test_vote_falls_back_to_propose_when_no_critique_record_this_round():
    state = _state_with_proposals(PROPOSALS)

    proposals = vote_module.ACTION._proposals(state)

    assert dict(proposals) == PROPOSALS
