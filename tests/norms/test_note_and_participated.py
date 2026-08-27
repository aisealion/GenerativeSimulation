from engine.llm_agents import _harvest_shortfall_clause, render_history


def _entry(agent_record, stock_kg_before=100.0, other_kg=5.0):
    return {
        "round": 1, "phase": "harvest", "stock_kg_before": stock_kg_before,
        "stock_kg_after_regrowth": 95.0,
        "agents": {"agent_0": agent_record, "agent_1": {"harvested_kg": other_kg}},
    }


def test_explicit_note_is_preferred_verbatim():
    record = {"effort": 0.9, "harvested_kg": 1.0, "note": "You drew 3kg from the reserve."}
    clause = _harvest_shortfall_clause(record, _entry(record))
    assert clause == " You drew 3kg from the reserve."


def test_participated_false_wins_over_a_note():
    record = {"effort": None, "harvested_kg": 0.0, "note": "some note", "participated": False}
    clause = _harvest_shortfall_clause(record, _entry(record))
    assert "weren't able to fish at all" in clause


def test_falls_back_to_inferred_sentence_when_no_note():
    # effort=1.0 against stock=100 -> baseline catch_from_effort(1.0, 100) = 5kg,
    # but harvested_kg=0.5 -> a real, uncommented shortfall an old-style norm
    # (one that never set "note") would otherwise leave unexplained.
    record = {"effort": 1.0, "harvested_kg": 0.5}
    clause = _harvest_shortfall_clause(record, _entry(record))
    assert "effort alone would normally have brought in" in clause


def test_no_shortfall_no_note_is_silent():
    record = {"effort": 0.1, "harvested_kg": 100.0}  # harvested far exceeds any plausible baseline
    clause = _harvest_shortfall_clause(record, _entry(record))
    assert clause == ""


def test_render_history_includes_the_note_via_round_record():
    runtime = {
        "rounds": [{
            "round": 1, "phase": "harvest", "stock_kg_before": 100.0,
            "stock_kg_after_regrowth": 95.0,
            "agents": {
                "agent_0": {
                    "effort": 0.9, "harvested_kg": 1.0, "reasoning": "",
                    "note": "That's more than your 1kg limit for the trip — the rest wasn't counted.",
                    "participated": True,
                },
                "agent_1": {"effort": 0.5, "harvested_kg": 5.0, "reasoning": "", "note": None, "participated": True},
            },
        }],
    }
    agents = {"agent_0": {"name": "Kai"}, "agent_1": {"name": "Mara"}}
    text = render_history("agent_0", 2, runtime, agents, window=5)
    assert "1kg limit for the trip" in text
