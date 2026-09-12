import pytest

from engine.llm_agents import render_action


def test_render_action_reads_the_owning_spec_own_template():
    text = render_action("harvest", stock_kg=280, carrying_capacity_kg=300, constraints_line="", stock_trend="x")
    assert "280kg" in text
    assert "300kg" in text
    assert text.startswith("It's time to go out on the lake.")


def test_render_action_finds_a_sub_template_owned_by_a_different_specs_templates_dict():
    text = render_action(
        "critique_response", current_policy="cap catches", current_operationalization="15kg/trip",
        question="Who holds the deposit?",
    )
    assert "Who holds the deposit?" in text
    assert "cap catches" in text


def test_render_action_falls_back_to_a_prompts_md_file_when_no_spec_owns_the_name():
    # "clarify" is genuinely not owned by any state/actions/*.json spec —
    # engine.clarify_norm runs outside the round action pipeline entirely
    # — so it must still resolve via actions/prompts/clarify.md.
    text = render_action("clarify", policy="cap catches", operationalization="15kg/trip", question="who enforces this?")
    assert "who enforces this?" in text


def test_render_action_raises_a_clear_error_for_an_unowned_and_fileless_name():
    with pytest.raises(FileNotFoundError):
        render_action("this_action_name_owns_nothing_and_has_no_md_file")
