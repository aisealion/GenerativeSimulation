from roles.roles import assign_role, current_holder, set_fact, end_fact, visible_facts


def test_exclusive_role_rotation_closes_the_previous_holder():
    """The documented assign_role() footgun: a rotating role's outgoing
    holder never actually closes if each call's `args` differs between
    holders (the default, args=[agent_id]) — set_fact() only terminates a
    record with the exact same (fluent, args) pair. exclusive=True forces
    a fixed args=[], making that mistake structurally unreachable. This
    used to only be exercised indirectly, via the old
    SimpleAgentAction/RoleGrant integration path (removed when actions/
    became declarative specs + handlers) — roles/roles.py itself had no
    direct test of its own most important rotation guarantee, so this is
    that test, not a port of anything."""
    fluents = []

    assign_role("_test_recorder", "agent_0", fluents, round_number=1, exclusive=True)
    assign_role("_test_recorder", "agent_1", fluents, round_number=2, exclusive=True)

    agent_0_record = next(r for r in fluents if r["holder"] == "agent_0")
    agent_1_record = next(r for r in fluents if r["holder"] == "agent_1")
    assert agent_0_record["terminated_round"] == 2
    assert agent_1_record["terminated_round"] is None
    assert current_holder(fluents, "_test_recorder", 2) == "agent_1"
    assert current_holder(fluents, "_test_recorder", 1) == "agent_0"


def test_non_exclusive_role_lets_every_agent_hold_it_simultaneously():
    fluents = []
    assign_role("_test_fisher_like", "agent_0", fluents, round_number=1)
    assign_role("_test_fisher_like", "agent_1", fluents, round_number=1)

    assert current_holder(fluents, "_test_fisher_like", 1) in ("agent_0", "agent_1")
    open_records = [r for r in fluents if r["fluent"] == "_test_fisher_like" and r["terminated_round"] is None]
    assert len(open_records) == 2


def test_end_fact_closes_without_opening_a_replacement():
    fluents = []
    set_fact(fluents, "_test_ban", ["agent_0"], "agent_0", 1,
              narration="A ban begins.", visibility="agent_only")
    end_fact(fluents, "_test_ban", ["agent_0"], 3, narration="The ban has been lifted.")

    record = fluents[0]
    assert record["terminated_round"] == 3
    assert record["end_narration"] == "The ban has been lifted."
    assert visible_facts(fluents, "agent_0", 2)  # still open at round 2
    assert not any(f["fluent"] == "_test_ban" for f in visible_facts(fluents, "agent_0", 4))
