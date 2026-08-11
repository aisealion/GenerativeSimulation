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
    agent = agents[agent_id]

    record = role_holder("fisher", agent_id, fluents, round_number)
    if record is None:
        raise RuntimeError(f"{agent_id} holds no 'fisher' role fluent at round {round_number}")

    role_directives = (ROOT / "prompts" / "role_directives" / "fisher.md").read_text().strip()
    persona_template = (ROOT / "prompts" / "persona_template.md").read_text()
    daily_status = f"This is round {round_number}."

    return persona_template.format(
        agent_name=agent["name"],
        personality_traits=agent["personality_traits"],
        role_directives=role_directives,
        daily_status=daily_status,
    ).strip()


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
