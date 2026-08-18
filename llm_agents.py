import json
import os
import re
import time
from pathlib import Path

import litellm

from call_log import log_call
from mechanisms.roles import role_holder

ROOT = Path(__file__).resolve().parent
LITELLM_PROXY_BASE_URL = "https://llm.uod.otago.ac.nz/v1"
DEFAULT_FISHER_MODEL = "litellm/Kimi-K2.5"


def _load_fisher_system_prompt():
    """The fisher character's system prompt used to live entirely inside
    the opencode agent definition (.opencode/agent/fisher.md); now that
    calls go direct, that file is kept as the single source for this text
    (not duplicated here) and its body (everything after the frontmatter)
    is read in as the system message."""
    text = (ROOT / ".opencode" / "agent" / "fisher.md").read_text()
    _, _, body = text.partition("---\n")
    _, _, body = body.partition("---")
    return body.strip()


FISHER_SYSTEM_PROMPT = _load_fisher_system_prompt()


def render_persona(agent_id, round_number, phase_name):
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
    relevant_memories = render_relevant_memories(agent_id, phase_name, round_number)

    return persona_template.format(
        agent_name=agent["name"],
        personality_traits=agent["personality_traits"],
        role_directives=role_directives,
        daily_status=daily_status,
        history=history,
        relevant_memories=relevant_memories,
    ).strip()


def render_relevant_memories(agent_id, phase_name, round_number):
    """Pre-fetched here, before the completion call — never exposed as a
    tool the fisher agent could call itself. The memory layer is optional,
    local-only infra for now (see write_memory_episodes() in simulate.py),
    so this degrades to the same placeholder text on any failure, not just
    when nothing relevant is found."""
    if not os.environ.get("NEO4J_URI"):
        return "(nothing notable comes to mind)"
    try:
        from memory.query import retrieve_memories
        from prompts.memory_phrasing import phrase_memory

        records = retrieve_memories(agent_id, phase_name, round_number)
        if not records:
            return "(nothing notable comes to mind)"
        return " ".join(phrase_memory(record) for record in records)
    except Exception as exc:
        print(f"  [memory retrieval skipped: {exc}]")
        return "(nothing notable comes to mind)"


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


MAX_ATTEMPTS = 3
CALL_DELAY_S = float(os.environ.get("LLM_CALL_DELAY_S", "2"))


def _resolve_completion_kwargs(model_spec):
    """FISHER_MODEL keeps the same 'provider/name' convention opencode.jsonc
    used (e.g. 'litellm/Kimi-K2.5', 'ollama/gpt-oss:120b') so existing env
    var values carry over — just routed to litellm's own provider syntax
    instead of opencode's."""
    provider, _, name = model_spec.partition("/")
    if provider == "litellm":
        return {
            "model": f"openai/{name}",
            "api_base": LITELLM_PROXY_BASE_URL,
            "api_key": os.environ["LITELLM_API_KEY"],
        }
    if provider == "ollama":
        ollama_host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
        api_base = ollama_host if ollama_host.startswith("http") else f"http://{ollama_host}"
        return {"model": f"ollama/{name}", "api_base": api_base}
    raise ValueError(
        f"unrecognized FISHER_MODEL provider {provider!r} in {model_spec!r} — expected 'litellm/...' or 'ollama/...'"
    )


def call_fisher_agent(agent_id, round_number, phase_name, **fields):
    prompt = render_persona(agent_id, round_number, phase_name) + "\n\n" + render_phase(phase_name, **fields)
    model_spec = os.environ.get("FISHER_MODEL", DEFAULT_FISHER_MODEL)
    completion_kwargs = _resolve_completion_kwargs(model_spec)

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        start = time.monotonic()
        raw_text = ""
        parsed = None
        error = None
        try:
            response = litellm.completion(
                messages=[
                    {"role": "system", "content": FISHER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                timeout=180,
                **completion_kwargs,
            )
            raw_text = response.choices[0].message.content or ""
            parsed = _parse_json_object(raw_text)
        except Exception as exc:
            error = str(exc)
        duration_s = time.monotonic() - start

        log_call(
            call="fisher",
            agent_id=agent_id,
            round=round_number,
            phase=phase_name,
            model=model_spec,
            attempt=attempt,
            duration_s=round(duration_s, 3),
            returncode=0 if error is None else 1,
            prompt=prompt,
            raw_response=raw_text,
            parsed_response=parsed,
            error=error,
        )

        if not error:
            time.sleep(CALL_DELAY_S)
            return parsed

        last_error = error
        print(f"  [{agent_id}/{phase_name} attempt {attempt}/{MAX_ATTEMPTS} failed: {error} — retrying]")
        time.sleep(CALL_DELAY_S)

    raise RuntimeError(
        f"fisher agent call failed for agent={agent_id} phase={phase_name} after {MAX_ATTEMPTS} attempts: {last_error}"
    )


def _parse_json_object(raw):
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise RuntimeError(f"no JSON object found in agent response: {raw!r}")
    return json.loads(match.group(0))
