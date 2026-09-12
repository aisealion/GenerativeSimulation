import pytest

from engine.institution.scheduler import compile_schedule, SchedulingConflictError


def test_compiles_a_satisfiable_after_chain_in_order():
    specs = {
        "vote": {"scheduling": {"after": "critique", "gate": "true"}},
        "harvest": {"scheduling": {"gate": "true"}},
        "critique": {"scheduling": {"after": "propose", "gate": "true"}},
        "propose": {"scheduling": {"after": "harvest", "gate": "true"}},
    }
    schedule = compile_schedule(specs)
    assert list(schedule) == ["harvest", "propose", "critique", "vote"]
    assert schedule["harvest"] == "true"


def test_before_constraint_is_equivalent_to_the_successors_after():
    specs = {
        "vote": {"scheduling": {"gate": "true"}},
        "harvest": {"scheduling": {"before": "propose", "gate": "true"}},
        "propose": {"scheduling": {"before": "vote", "gate": "true"}},
    }
    schedule = compile_schedule(specs)
    assert list(schedule) == ["harvest", "propose", "vote"]


def test_ties_broken_by_declaration_order():
    specs = {
        "b": {"scheduling": {"gate": "true"}},
        "a": {"scheduling": {"gate": "true"}},
        "c": {"scheduling": {"gate": "true"}},
    }
    assert list(compile_schedule(specs)) == ["b", "a", "c"]


def test_default_gate_is_true_when_unspecified():
    specs = {"solo": {}}
    assert compile_schedule(specs) == {"solo": "true"}


def test_a_new_action_can_be_inserted_between_two_existing_ones():
    specs = {
        "harvest": {"scheduling": {"gate": "true"}},
        "propose": {"scheduling": {"after": "harvest", "gate": "true"}},
        "inspect": {"scheduling": {"after": "harvest", "before": "propose", "gate": "holdsAt(inspector)"}},
    }
    schedule = compile_schedule(specs)
    assert list(schedule) == ["harvest", "inspect", "propose"]


def test_cycle_raises_scheduling_conflict_error():
    specs = {
        "a": {"scheduling": {"after": "b", "gate": "true"}},
        "b": {"scheduling": {"after": "a", "gate": "true"}},
    }
    with pytest.raises(SchedulingConflictError, match="cycle"):
        compile_schedule(specs)


def test_unknown_after_target_raises_scheduling_conflict_error():
    specs = {"a": {"scheduling": {"after": "nonexistent", "gate": "true"}}}
    with pytest.raises(SchedulingConflictError, match="unknown action"):
        compile_schedule(specs)
