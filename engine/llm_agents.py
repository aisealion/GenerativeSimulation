import json
import os
import re
import time
from pathlib import Path

import litellm

from engine.call_log import log_call
from engine.physics import alive_agent_ids, catch_from_effort, CONSUMPTION_KG
from roles.roles import role_holder, visible_facts


def _patch_litellm_message_rebuild():
    """litellm==1.97.0's Message type has a pydantic forward reference
    (ChatCompletionReasoningSummaryTextBlock, via ChatCompletionReasoningItem)
    that never gets resolved on Python 3.10 — reproduced independent of any
    package version (litellm/pydantic/pydantic-core and every one of
    pydantic's own direct dependencies pinned identical to a known-working
    Python 3.11 install; still fails identically on 3.10). A genuine litellm
    bug: on 3.11 whatever import path runs happens to leave the type
    resolvable by the time Message's schema is built; on 3.10 it doesn't,
    and every completion() call fails with "Message is not fully defined
    ... call Message.model_rebuild()" before a request is even sent.
    Bringing the two referenced types into scope and forcing a rebuild once
    here fixes it for the rest of the process — confirmed via a real
    completion() call on a from-scratch Python 3.10.20 venv with this
    project's exact pinned dependency set. Harmless no-op on Python
    versions where the bug doesn't occur."""
    try:
        from litellm.types.llms.openai import (
            ChatCompletionReasoningItem,  # noqa: F401
            ChatCompletionReasoningSummaryTextBlock,  # noqa: F401
        )
        from litellm.types.utils import Message

        Message.model_rebuild(force=True)
    except Exception as exc:
        print(f"  [litellm Message.model_rebuild() workaround skipped: {exc}]")


_patch_litellm_message_rebuild()

ROOT = Path(__file__).resolve().parent.parent
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


def render_persona(agent_id, round_number, action_name):
    agents = json.loads((ROOT / "constants" / "agents.json").read_text())
    fluents = json.loads((ROOT / "state" / "fluents.json").read_text())
    events = json.loads((ROOT / "state" / "events.json").read_text())
    runtime = json.loads((ROOT / "state" / "runtime.json").read_text())
    config = json.loads((ROOT / "state" / "config.json").read_text())
    agent = agents[agent_id]

    record = role_holder("fisher", agent_id, fluents, round_number)
    if record is None:
        raise RuntimeError(f"{agent_id} holds no 'fisher' role fluent at round {round_number}")

    role_directives = render_role_directives(agent_id, fluents, round_number)
    persona_template = (ROOT / "prompts" / "persona_template.md").read_text()
    daily_status = f"This is round {round_number}."
    survival_status = render_survival_status(agent_id, runtime)
    history = render_history(
        agent_id, round_number, runtime, agents, config.get("history_window_rounds", 5)
    )
    notices = render_notices(agent_id, round_number, fluents, events)
    relevant_memories = render_relevant_memories(agent_id, action_name, round_number)

    return persona_template.format(
        agent_name=agent["name"],
        personality_traits=agent["personality_traits"],
        role_directives=role_directives,
        daily_status=daily_status,
        survival_status=survival_status,
        history=history,
        notices=notices,
        relevant_memories=relevant_memories,
    ).strip()


def render_role_directives(agent_id, fluents, round_number):
    """Every `prompts/role_directives/{role}.md` whose role `agent_id`
    currently holds, concatenated in `state/institution.json`'s own
    `"roles"` catalog order — generalizes what used to be a hardcoded
    `fisher.md`-only read. Every agent holds `"fisher"` from round 0 (see
    `generate_agents.py`), which stays first in that catalog, so this
    always includes at least the same text render_persona() always
    rendered; a role a norm-implementer later registers and assigns (a
    rotating recorder/treasurer/steward/monitor) now gets its own
    directive rendered too, with no code change required — this is the
    actual mechanism `.opencode/agent/norm-implementer.md`'s "the
    recorder's own role_directives/recorder.md must make this
    responsibility explicit" instruction depends on; before this function
    existed, that file was written but never read for anything but
    `fisher`.

    Raises FileNotFoundError for a role this agent actually holds but
    that has no directive file — deliberately not a silent skip, since a
    role assigned with no way for its holder to learn what it means is
    exactly the gap this function exists to close (see also
    `engine.simulate.norm_implementation_institution_errors()`'s matching
    pre-commit drift check, which catches this before a round ever
    commits, not just the first time the role is actually held)."""
    institution = json.loads((ROOT / "state" / "institution.json").read_text())
    texts = []
    for role_name in institution.get("roles", {}):
        if role_holder(role_name, agent_id, fluents, round_number) is None:
            continue
        path = ROOT / "prompts" / "role_directives" / f"{role_name}.md"
        if not path.is_file():
            raise FileNotFoundError(
                f"{agent_id} holds role {role_name!r} but prompts/role_directives/"
                f"{role_name}.md doesn't exist"
            )
        texts.append(path.read_text().strip())
    return " ".join(texts)


def render_survival_status(agent_id, runtime):
    """Fishing isn't just for profit — every fisher owes a fixed cost just
    to feed themselves each trip, tracked as a running balance that goes
    back to round 0, not reset each round. Ties directly to the mechanic in
    actions/handlers/harvest.py: apply_consumption()/is_dead() decide the
    same balance this renders. Deliberately repeated on every action's prompt,
    not just harvest's, matching how Gupta et al.'s CPRAgent restates this
    same survival framing in every one of its own prompt templates
    (strategy/punishment/norm-update/vote), not only the harvest one."""
    balance = runtime.get("payoff", {}).get(agent_id, 0.0)
    return (
        f"Fishing isn't just for profit — you need roughly {CONSUMPTION_KG:.0f}kg a trip just to "
        f"keep yourself fed. Your running reserves stand at {balance:.1f}kg right now; if that "
        f"ever drops below zero, you won't be able to keep fishing."
    )


def render_notices(agent_id, round_number, fluents, events=()):
    """Everything currently true about this agent (or the community), plus
    anything that happened exactly this round, that some mechanism wanted
    surfaced — bans, obligations, statuses, an object mutation, whatever a
    future norm invents. Never interprets a raw state value itself: it only
    concatenates already-phrased text — a currently-active fluent's own
    `narration` (visible_facts()) and a point-in-time event's own `text`
    (engine.institution.events.visible_events()) — which the mechanism
    that wrote it authored at the moment it happened (mirroring how
    actions/handlers/*.py's memory_writes() already hands the memory layer
    already-phrased text rather than raw fields). `events` defaults to ()
    so a caller that hasn't been updated to pass it yet degrades to
    fact-only notices rather than raising."""
    from engine.institution.events import visible_events

    facts = visible_facts(fluents, agent_id, round_number)
    live_events = visible_events(events, agent_id, round_number)
    texts = [fact["narration"] for fact in facts] + [event["text"] for event in live_events]
    if not texts:
        return "(nothing notable comes to mind)"
    return " ".join(texts)


def render_relevant_memories(agent_id, action_name, round_number):
    """Pre-fetched here, before the completion call — never exposed as a
    tool the fisher agent could call itself. The memory layer is optional,
    local-only infra for now (see write_memory_episodes() in simulate.py),
    so this degrades to the same placeholder text on any failure, not just
    when nothing relevant is found."""
    if not os.environ.get("NEO4J_URI"):
        return "(nothing notable comes to mind)"
    try:
        from engine.memory.query import retrieve_memories
        from prompts.memory_phrasing import phrase_memory

        records = retrieve_memories(agent_id, action_name, round_number)
        if not records:
            return "(nothing notable comes to mind)"
        return " ".join(phrase_memory(record) for record in records)
    except Exception as exc:
        print(f"  [memory retrieval skipped: {exc}]")
        return "(nothing notable comes to mind)"


def _harvest_shortfall_clause(mine_record, entry):
    """Rules (actions/rules/harvest/*.py, orchestrated by a harvest-scoped
    RuleSet — engine/institution/rules.py) enforce themselves by
    reducing/zeroing an agent's harvested_kg (a cap, a ban, a reserve
    draw) — this is what makes sure the affected agent actually learns
    that, rather than only ever seeing the resulting kg number with no way
    to tell an enforced outcome apart from one they freely chose. A rule's
    own after_agent()-patched note (round_record["agents"][agent_id]
    ["note"]) is preferred verbatim when a rule authored one — it's the
    specific, in-world sentence that rule chose (an over-cap trim, a
    reserve top-up). Falls back to a generic derived sentence when no rule
    bothered to explain itself: catch_from_effort() is pure and
    mechanism-agnostic, so re-running it on the agent's own recorded
    effort against that round's starting stock gives what their effort
    alone would have produced with nothing else in play. If the agent
    wasn't even asked that round (a live ban, via some rule's own
    is_eligible() hook — not something inferable from numbers alone),
    "participated": False is set explicitly by actions/handlers/harvest.py;
    anything else defaults to participated.
    """
    if mine_record.get("participated") is False:
        return " You weren't able to fish at all this round — something about the community's current rules held you back."

    if mine_record.get("note"):
        return f" {mine_record['note'].strip()}"

    baseline_kg = catch_from_effort(mine_record["effort"], entry["stock_kg_before"])
    shortfall = baseline_kg - mine_record["harvested_kg"]
    if shortfall > max(0.5, 0.05 * baseline_kg):
        return (
            f" That's less than your effort alone would normally have brought in "
            f"(more like {baseline_kg:.0f}kg) — something about the community's "
            f"current rules held some of it back."
        )
    return ""


def render_history(agent_id, round_number, runtime, agents, window):
    past_rounds = sorted({r["round"] for r in runtime["rounds"] if r["round"] < round_number})
    past_rounds = past_rounds[-window:]
    if not past_rounds:
        return "This is your first time out on the lake."

    lines = []
    for r in past_rounds:
        for entry in (e for e in runtime["rounds"] if e["round"] == r):
            if entry["action"] == "harvest":
                mine_record = entry["agents"][agent_id]
                mine = mine_record["harvested_kg"]
                total_others = sum(
                    a["harvested_kg"] for oid, a in entry["agents"].items() if oid != agent_id
                )
                lines.append(
                    f"Round {r}: you brought in {mine:.0f}kg; the rest of the community brought "
                    f"in {total_others:.0f}kg between them. The lake stood at "
                    f"{entry['stock_kg_after_regrowth']:.0f}kg afterward."
                    f"{_harvest_shortfall_clause(mine_record, entry)}"
                )
            elif entry["action"] == "propose":
                mine = entry["proposals"][agent_id]["policy"]
                num_others = len(entry["proposals"]) - 1
                lines.append(
                    f'Round {r}: you proposed "{mine}", alongside {num_others} other proposal(s) '
                    f"from the rest of the community."
                )
            elif entry["action"] == "vote":
                winner_id = entry["winning_proposer"]
                who = "your" if winner_id == agent_id else f"{agents[winner_id]['name']}'s"
                tally = entry["tally"]
                winner_index = entry["winner_index"]
                # tally's keys are ints in a freshly-computed round_record but
                # become JSON-object string keys once written to and reread
                # from state/runtime.json — accept either.
                winner_votes = tally.get(winner_index, tally.get(str(winner_index)))
                total_votes = sum(tally.values())
                lines.append(
                    f"Round {r}: the community voted, and {who} proposal won "
                    f"({winner_votes}/{total_votes})."
                )

    return "Here's what's happened so far:\n" + "\n".join(f"- {line}" for line in lines)


def render_action(action_name, **fields):
    """The template for `action_name` is looked up in this order:

    1. `state/actions/{action_name}.json`'s own `prompt.template` — the
       normal case for a real action (harvest/propose/vote/...). This is
       where a new action's prompt lives: no separate file, edited right
       alongside the spec that names it.
    2. Any `state/actions/*.json` spec's `prompt.templates` dict, if it
       has a key matching `action_name` — for a sub-step of a multi-call
       action that isn't itself a top-level action (critique's own
       "critique_response"/"critique_finalize" dialogue steps, owned by
       critique.json but not critique's own action_name).
    3. `actions/prompts/{action_name}.md`, if none of the above match —
       for a prompt that genuinely isn't owned by any one action (e.g.
       "clarify", used by the standalone engine/clarify_norm.py tool,
       outside the round action pipeline entirely).

    Raises FileNotFoundError if none of the three resolve — same failure
    mode `.read_text()` on a missing .md file already had.
    """
    template = _action_template(action_name)
    if template is None:
        template = (ROOT / "actions" / "prompts" / f"{action_name}.md").read_text()
    return template.format(**fields).strip()


def _action_template(action_name):
    actions_dir = ROOT / "state" / "actions"
    own_spec_path = actions_dir / f"{action_name}.json"
    if own_spec_path.exists():
        own_template = json.loads(own_spec_path.read_text()).get("prompt", {}).get("template")
        if own_template is not None:
            return own_template
    for spec_path in sorted(actions_dir.glob("*.json")):
        templates = json.loads(spec_path.read_text()).get("prompt", {}).get("templates", {})
        if action_name in templates:
            return templates[action_name]
    return None


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


def call_fisher_agent(agent_id, round_number, action_name, **fields):
    prompt = render_persona(agent_id, round_number, action_name) + "\n\n" + render_action(action_name, **fields)
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
            action=action_name,
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
        print(f"  [{agent_id}/{action_name} attempt {attempt}/{MAX_ATTEMPTS} failed: {error} — retrying]")
        time.sleep(CALL_DELAY_S)

    raise RuntimeError(
        f"fisher agent call failed for agent={agent_id} action={action_name} after {MAX_ATTEMPTS} attempts: {last_error}"
    )


CRITIQUE_SYSTEM_PROMPT = """You are an institutional-design critic reviewing a proposed community rule
before it goes to a vote. Your ONLY job is to identify institutional
details the proposal leaves unspecified — who holds something, when it
happens, how much, what happens on violation, who decides. You are not a
rule-maker: you must NEVER suggest what the answer should be, propose a
specific value or mechanism, or recommend adding anything the proposal
doesn't already imply. Ask only "what does this leave unanswered?" — never
"you should also...".

Good: "The proposal doesn't specify who holds the deposit."
Good: "The proposal doesn't say when the deposit is returned."
Bad: "You should make the deposit 5kg of fish." (this invents content —
never do this)
Bad: "You should also add a punishment for repeat violations." (this
invents content — never do this)

You'll also be told what institutional mechanisms already exist (actions,
tracked state, active rules) and how many fishers are in the community.
Use this only to ask sharper, more concrete questions — e.g. "there's no
existing mechanism for holding a deposit — who would hold it?", or "the
proposal says fishers must comply, but doesn't say whether that means all
of the community's current fishers or just some" — never to suggest which
existing mechanism should be reused, or to propose adding one yourself.
Pointing out that something is missing is your job; deciding what fills
the gap is never your job, whether the answer would be new or already
exists.

If the proposal is already clear enough to implement (every institutional
detail a reasonable person would need is answered), say so — don't
manufacture a question just to have one.

Respond with ONLY this JSON object, nothing else:
{"status": "SUFFICIENT"} if nothing important is missing, or
{"status": "QUESTION", "question": "<one specific missing-detail question, in plain language>"}
"""


def _critique_context():
    """Plain-language summary of the current institution and community
    size, handed to the critique agent so its questions can reference what
    actually exists (an existing action, an existing tracked state field,
    how many fishers there are) instead of guessing blind. Reads directly
    from disk, the same convention render_persona() already uses for its
    own context-gathering — the critique agent has no persona/state passed
    to it any other way. Not subject to prompts/'s fourth-wall rule (that
    applies to fisher-facing text only) — this agent is explicitly an
    out-of-character analytical role, same footing as the norm-implementer/
    evaluator, so plain internal names are fine here. Degrades gracefully
    (empty-but-valid summary) if state/institution.json doesn't exist yet
    rather than raising — this call must never be the reason a round fails."""
    agents = json.loads((ROOT / "constants" / "agents.json").read_text())
    runtime = json.loads((ROOT / "state" / "runtime.json").read_text())
    config = json.loads((ROOT / "state" / "config.json").read_text())
    institution_path = ROOT / "state" / "institution.json"
    institution = json.loads(institution_path.read_text()) if institution_path.is_file() else {}

    agent_ids = alive_agent_ids(agents, runtime)
    action_names = ", ".join(sorted(institution.get("actions", {}))) or "none recorded"
    state_fields = institution.get("state", {})
    state_summary = "; ".join(
        f"{group}: {', '.join(fields)}" for group, fields in state_fields.items()
    ) or "none recorded"
    norms = config.get("norms", [])
    norms_summary = ", ".join(n.get("type", "?") for n in norms) if norms else "none currently active"

    return (
        f"There are currently {len(agent_ids)} fishers active in the community "
        f"(out of {len(agents)} total ever in it). Existing institutional actions "
        f"(rounds of decision-making already in place): {action_names}. State already "
        f"tracked: {state_summary}. Currently active community rules: {norms_summary}. "
        f"Current lake stock: {runtime.get('stock_kg', 'unknown')}kg."
    )


def call_critique_agent(policy, operationalization, history, round_number=None, proposer_id=None):
    """Reviews one proposal for missing institutional specification before
    it goes to a vote — a fixed, neutral role, deliberately with no fisher
    persona/personality/history rendering, so it brings nothing to the
    proposal except the question of whether it's specified enough to
    implement. Barred from prescribing normative content by
    CRITIQUE_SYSTEM_PROMPT — it identifies gaps, it never fills them; that
    boundary is enforced only by the prompt, the same posture every other
    behavioral constraint on a model call in this project already has.

    Stateless per call, like every model call here — `history` (a list of
    prior {"question", "answer", "revised_policy", "revised_operationalization"}
    dicts from this same proposal's earlier exchanges) is reconstructed
    into genuine conversation turns each call, not summarized, so the
    model sees the actual back-and-forth rather than a paraphrase of it.
    `round_number`/`proposer_id` are for logging only (call_call()'s own
    round/agent_id columns) — the institution/roster context (see
    _critique_context()) is read fresh from disk on every call rather than
    passed in, so it reflects whatever a same-round earlier proposal's own
    critique loop may have already changed (nothing currently does, but
    reading fresh costs nothing and avoids relying on that staying true)."""
    messages = [{"role": "system", "content": CRITIQUE_SYSTEM_PROMPT}]
    messages.append({
        "role": "user",
        "content": (
            f"Context: {_critique_context()}\n\n"
            f"Proposed policy: {policy}\n"
            f"Operationalization: {operationalization}\n\n"
            "Review this proposal."
        ),
    })
    for turn in history:
        messages.append({
            "role": "assistant",
            "content": json.dumps({"status": "QUESTION", "question": turn["question"]}),
        })
        messages.append({
            "role": "user",
            "content": (
                f"The proposer answered: {turn['answer']}\n"
                f"Revised policy: {turn['revised_policy']}\n"
                f"Revised operationalization: {turn['revised_operationalization']}"
            ),
        })

    model_spec = os.environ.get("FISHER_MODEL", DEFAULT_FISHER_MODEL)
    completion_kwargs = _resolve_completion_kwargs(model_spec)

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        start = time.monotonic()
        raw_text = ""
        parsed = None
        error = None
        try:
            response = litellm.completion(messages=messages, timeout=180, **completion_kwargs)
            raw_text = response.choices[0].message.content or ""
            parsed = _parse_json_object(raw_text)
        except Exception as exc:
            error = str(exc)
        duration_s = time.monotonic() - start

        log_call(
            call="critique",
            agent_id=proposer_id,
            round=round_number,
            action="critique",
            model=model_spec,
            attempt=attempt,
            duration_s=round(duration_s, 3),
            returncode=0 if error is None else 1,
            prompt=messages[-1]["content"],
            raw_response=raw_text,
            parsed_response=parsed,
            error=error,
        )

        if not error:
            time.sleep(CALL_DELAY_S)
            return parsed

        last_error = error
        print(f"  [critique/{proposer_id} attempt {attempt}/{MAX_ATTEMPTS} failed: {error} — retrying]")
        time.sleep(CALL_DELAY_S)

    raise RuntimeError(f"critique agent call failed for proposer={proposer_id} after {MAX_ATTEMPTS} attempts: {last_error}")


def _parse_json_object(raw):
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise RuntimeError(f"no JSON object found in agent response: {raw!r}")
    return json.loads(match.group(0))
