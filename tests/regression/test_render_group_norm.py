"""render_group_norm() (engine/llm_agents.py, 2026-09-26) surfaces the
community's currently-adopted policy in every fisher prompt, regardless of
action — replacing render_survival_status() as the "fixed" scenario-
framing section of persona_template.md, by request (matching the
CPRAgent-style prompt this codebase already references elsewhere)."""
import engine.llm_agents as llm_agents_module
from engine.llm_agents import render_group_norm


def test_returns_a_placeholder_before_any_norm_has_been_adopted(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_agents_module, "ROOT", tmp_path)
    # norm.txt deliberately absent — round 0/early rounds, before any vote.

    assert render_group_norm() == "(no community policy has been adopted yet)"


def test_returns_norm_txts_own_content_once_a_norm_is_adopted(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_agents_module, "ROOT", tmp_path)
    (tmp_path / "norm.txt").write_text(
        "Policy: no more than 10kg per trip.\n\nOperationalization: verifiers weigh every catch.\n"
    )

    assert render_group_norm() == (
        "Policy: no more than 10kg per trip.\n\nOperationalization: verifiers weigh every catch."
    )
