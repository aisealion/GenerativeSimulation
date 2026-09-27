"""render_action() / _action_template() (engine/llm_agents.py) — the exact
mechanism norm_implementation_runtime_errors()'s subprocess smoke test
now calls for every generic_agent_decision action (2026-09-27), after a
live run crashed the ENTIRE simulation process on round 2 trying to
actually run a round-1-committed action. Every existing check (compile,
institution registration, resolve_handler()) had passed cleanly on all six
new actions that round, since none of them ever call render_action() —
that's what actually broke, with an uncaught FileNotFoundError: 'prompt'
had been written as a nested key under 'execution' instead of a top-level
sibling of it. A second, independent bug in the same six specs (an
unescaped literal JSON example in the template, which str.format() tries
to parse as substitution fields) surfaces the same way once the first is
fixed.

These test render_action()/_action_template() directly rather than
through norm_implementation_runtime_errors()'s own subprocess — that
function shells out to a fresh process relying on cwd genuinely being the
repo root (so its own sys.path.insert(0, '.') resolves real packages),
which doesn't compose with monkeypatching ROOT for isolation the way a
same-process call does."""
import json

import pytest

import engine.llm_agents as llm_agents_module
from engine.llm_agents import render_action


def _write_spec(tmp_path, name, spec):
    actions_dir = tmp_path / "state" / "actions"
    actions_dir.mkdir(parents=True, exist_ok=True)
    (actions_dir / f"{name}.json").write_text(json.dumps(spec))


def test_prompt_nested_under_execution_is_never_found(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_agents_module, "ROOT", tmp_path)
    # The exact real mistake: 'prompt' placed inside 'execution' instead of
    # as a top-level sibling key — _action_template() only ever looks at
    # the top-level "prompt" key, so this is invisible to it.
    _write_spec(tmp_path, "record_catch", {
        "name": "record_catch",
        "execution": {
            "handler": "generic_agent_decision",
            "prompt": {"fields": ["answer"], "template": 'Answer.\n{{"answer": "..."}}\n'},
        },
    })

    with pytest.raises(FileNotFoundError):
        render_action("record_catch", answer="placeholder")


def test_unescaped_json_example_braces_break_str_format(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_agents_module, "ROOT", tmp_path)
    # 'prompt' correctly at the top level this time, but the literal JSON
    # example uses single braces — str.format() tries to treat them as
    # substitution fields and raises KeyError instead of leaving them as
    # literal text.
    _write_spec(tmp_path, "record_catch", {
        "name": "record_catch",
        "prompt": {"fields": ["answer"], "template": 'Answer.\n{"answer": "..."}\n'},
        "execution": {"handler": "generic_agent_decision"},
    })

    with pytest.raises(KeyError):
        render_action("record_catch", answer="placeholder")


def test_correctly_shaped_spec_renders_cleanly(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_agents_module, "ROOT", tmp_path)
    _write_spec(tmp_path, "record_catch", {
        "name": "record_catch",
        "prompt": {"fields": ["answer"], "template": 'Answer.\n{{"answer": "{answer}"}}\n'},
        "execution": {"handler": "generic_agent_decision"},
    })

    text = render_action("record_catch", answer="42")

    assert text == 'Answer.\n{"answer": "42"}'
