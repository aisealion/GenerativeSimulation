import json
import os
import re
import subprocess
import time
from pathlib import Path

from call_log import log_call
from mechanisms.roles import role_holder

ROOT = Path(__file__).resolve().parent


def render_persona(agent_id, round_number):
    agents = json.loads((ROOT / "state" / "agents.json").read_text())
    fluents = json.loads((ROOT / "state" / "fluents.json").read_text())
    runtime = json.loads((ROOT / "state" / "runtime.json").read_text())
    config = json.loads((ROOT / "state" / "config.json").read_text())
    agent = agents[agent_id]

    record = role_holder("fisher", agent_id, fluents, round_number)
    if record is None:
        raise RuntimeError(f"{agent_id} holds no 'fisher' role fluent at round {round_number}")

    role_directives = (ROOT / "prompts" / "role_directives" / "fisher.md").read_text().strip()
    persona_template = (ROOT / "prompts" / "persona_template.md").read_text()
    daily_status = f"This is round {round_number}."
    history = render_history(
        agent_id, round_number, runtime, agents, config.get("history_window_rounds", 5)
    )

    return persona_template.format(
        agent_name=agent["name"],
        personality_traits=agent["personality_traits"],
        role_directives=role_directives,
        daily_status=daily_status,
        history=history,
    ).strip()


def render_history(agent_id, round_number, runtime, agents, window):
    other_id = next(a for a in agents if a != agent_id)
    other_name = agents[other_id]["name"]

    past_rounds = sorted({r["round"] for r in runtime["rounds"] if r["round"] < round_number})
    past_rounds = past_rounds[-window:]
    if not past_rounds:
        return "This is your first time out on the lake."

    lines = []
    for r in past_rounds:
        for entry in (e for e in runtime["rounds"] if e["round"] == r):
            if entry["phase"] == "harvest":
                mine = entry["agents"][agent_id]["harvested_kg"]
                theirs = entry["agents"][other_id]["harvested_kg"]
                lines.append(
                    f"Round {r}: you brought in {mine:.0f}kg, {other_name} brought in "
                    f"{theirs:.0f}kg. The lake stood at {entry['stock_kg_after_regrowth']:.0f}kg afterward."
                )
            elif entry["phase"] == "propose":
                mine = entry["proposals"][agent_id]["policy"]
                theirs = entry["proposals"][other_id]["policy"]
                lines.append(f'Round {r}: you proposed "{mine}" and {other_name} proposed "{theirs}".')
            elif entry["phase"] == "vote":
                who = "your" if entry["winning_proposer"] == agent_id else f"{other_name}'s"
                lines.append(
                    f"Round {r}: the two of you voted, and {who} proposal won "
                    f"({entry['votes_for_a']}-{entry['votes_for_b']})."
                )

    return "Here's what's happened so far:\n" + "\n".join(f"- {line}" for line in lines)


def render_phase(phase_name, **fields):
    template = (ROOT / "prompts" / "phases" / f"{phase_name}.md").read_text()
    return template.format(**fields).strip()


def call_fisher_agent(agent_id, round_number, phase_name, **fields):
    prompt = render_persona(agent_id, round_number) + "\n\n" + render_phase(phase_name, **fields)

    cmd = ["opencode", "run", "--agent", "fisher"]
    model = os.environ.get("OPENCODE_MODEL")
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)

    start = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=ROOT)
    duration_s = time.monotonic() - start

    parsed = None
    error = None
    if result.returncode != 0:
        error = result.stderr.strip()
    else:
        try:
            parsed = _parse_json_object(result.stdout)
        except Exception as exc:
            error = str(exc)

    log_call(
        call="fisher",
        agent_id=agent_id,
        round=round_number,
        phase=phase_name,
        model=model,
        duration_s=round(duration_s, 3),
        returncode=result.returncode,
        prompt=prompt,
        raw_response=result.stdout,
        parsed_response=parsed,
        error=error,
    )

    if error:
        raise RuntimeError(f"opencode run failed for agent={agent_id} phase={phase_name}: {error}")
    return parsed


def _parse_json_object(raw):
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise RuntimeError(f"no JSON object found in agent response: {raw!r}")
    return json.loads(match.group(0))
