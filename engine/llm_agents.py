import json
import os
import re
import sys
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
    the opencode agent definition (.opencode/agent/fisher.md, back when
    fisher calls went through opencode); now that calls go direct via
    litellm, that file was dead weight sitting in the opencode-agent
    directory pretending to be an agent nothing ever invoked — moved to
    prompts/fisher_system_prompt.md (plain text, no frontmatter needed)
    as the single source of this text."""
    return (ROOT / "prompts" / "fisher_system_prompt.md").read_text().strip()


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
    rendered; a role a norm-engineer later registers and assigns (a
    rotating recorder/treasurer/steward/monitor) now gets its own
    directive rendered too, with no code change required — this is the
    actual mechanism `.opencode/agents/norm-engineer.md`'s "the
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
    out-of-character analytical role, same footing as the norm pipeline
    agents (architect/engineer/auditor), so plain internal names are fine
    here. Degrades gracefully
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


NORM_ARCHITECT_LOG_PATH = ROOT / "ops" / "logs" / "norm_architect.jsonl"
MAX_ARCHITECT_ATTEMPTS = 3
ARCHITECT_CALL_DELAY_S = float(os.environ.get("LLM_CALL_DELAY_S", "2"))

# 2026-09-22: norm-architect used to run as a full opencode agent (bash,
# edit, glob, grep, read, codegraph_explore, write) — a real HPC run
# showed every single invocation failing instantly (~2s, zero tool calls)
# with a 400 API error: "registry.ollama.ai/library/deepseek-r1-...
# does not support tools". Root cause, confirmed against upstream reports
# (github.com/sst/opencode/issues/2123, github.com/ollama/ollama/issues/
# 12719): Ollama's default deepseek-r1 registry tags predate DeepSeek's
# own May 2025 tool-calling update and simply don't ship a chat template
# that supports the OpenAI `tools` request field — opencode always sends
# one (it's an inherently agentic framework), so every call was rejected
# before the model ever saw the prompt, regardless of context/output size
# tuning. But norm-architect never actually needed real filesystem
# access: its whole job is reading a fixed bundle of text (norm.txt +
# the institution contracts) and producing text (one pytest file + a
# JSON requirements checklist) — exactly what a plain, tool-free
# completion call already does for the fisher/critique agents above.
# litellm.completion() only sends a `tools` field when the caller passes
# one; since this function never does, this call is immune to the same
# 400 regardless of the model's own template support.
NORM_ARCHITECT_SYSTEM_PROMPT = """You are the Norm Architect for a multi-agent fishery simulation. Each
round you are given norm.txt (a Policy statement plus the community's
Operationalization of it) and a fixed bundle of reference material. Your
job is reading, reasoning, and test-authoring ONLY — never
implementation. You have NO TOOLS and no filesystem access: you cannot
read, write, or execute anything yourself. Everything you need is in this
message; everything you produce must be in your response text, nothing
else. Never claim to have read or written a file, called a tool, or run a
command — you cannot.

You are not the norm's author: never invent obligations, rights,
sanctions, or objectives its own text doesn't already entail. Extract
EVERY atomic actor+verb+object requirement from the Operationalization,
clause by clause — never a paraphrase of a whole sentence. Two
verb-phrases sharing one actor are still two requirements. Err toward
over-splitting. Distinguish genuine agent judgment (weighs, judges,
inspects, decides, reviews-and-rules, verifies, contests, appeals,
testifies, exercises discretion) from deterministic arithmetic, and
either from inventory (a noun that's state, not a decision) — route by
what the requirement IS, never by which path is cheaper. Reuse an
existing rule/object/action type (see the institution catalog in your
reference bundle) before inventing a new one.

## Critique, not just clarify

When a requirement's clarity is AMBIGUOUS or INCOMPLETE, or you find two
clauses of norm.txt in genuine tension, don't silently pick a best-effort
reading. Put it in your response's "open_critiques" array (see JSON
format below) as a real critique of the norm's own text — name the
specific gap or contradiction plainly ("clause 2 requires X but clause 4
implies not-X — which governs, and why wasn't this addressed?"), not a
vague "what did you mean." You'll be given the proposer's answer in a
follow-up message and asked to finalize your tests and checklist using
it. Never ask for approval or code — only what the rule means.

## Write the failing test suite

Write ONE complete pytest file (not several) covering every requirement.
It must fail red against the current code — nothing implementing this
round's norm exists yet, so a well-written test simply won't pass until
someone builds it. Write however many test cases each requirement
actually needs — never just one: at minimum the compliant path, the
non-compliant/penalty path wherever the requirement implies a violation,
and boundary cases the norm's own numbers imply (exactly at a threshold,
just under it, just over it). Build the fabricated `state` realistically,
through the shapes your reference bundle's contracts describe — exercise
the real handler/rule/action machinery, never a bare unit test of a class
in isolation. A structural requirement (a new rule type actually
activated in state/config.json, a new role actually assignable) needs its
own test too, not just the functional behavior once triggered.

## Output format — exactly two fenced blocks, nothing after the second one

A fenced ```python block containing the complete test file, then a fenced
```json block with this shape:

```json
{
  "requirements": [
    {
      "requirement": "...", "purpose": "...", "actor": "...", "level": 1,
      "action_attached_to": "harvest", "action_or_decision": "...",
      "existing_owner_or_new": "new rule type: actions/rules/harvest/example.py",
      "inputs": "...", "outputs": "...", "state_read": "...",
      "state_changed": ["state/config.json"], "timing_frequency": "...",
      "participation": "...", "gate": "...", "institutional_consequence": "...",
      "agent_visible_information": "...", "verification": ["the test function name(s) covering it"],
      "clarity": "CLEAR", "clarity_critique": null, "clarity_resolution": null
    }
  ],
  "open_critiques": [
    {"requirement": "...", "critique_question": "..."}
  ]
}
```
A requirement routed to a new institutional object additionally carries
`object_type_name`, `purpose`, `ownership`, `fields`, `operations`,
`permissions`, `visibility`, `custom_logic`, `lifecycle`, `instances`. One
routed to a new action additionally carries `action_name`, `level` (2/4),
`actor`, `purpose`, `decision_or_action`, `inputs`, `output`,
`state_changes`, `after`, `frequency`, `gate`, `enforcement`,
`interaction`. `open_critiques` is `[]` if nothing is unresolved.
`requirements` includes every requirement, even one you couldn't fully
design — give it `"existing_owner_or_new": "NOT_DESIGNED_THIS_ROUND"` plus
a `"reason"` field rather than omitting it."""


def _build_norm_architect_prompt(round_number, norm_text, context_bundle, resolutions=None):
    sections = [
        f"This is round {round_number}.",
        "## norm.txt (this round's adopted Policy + Operationalization)",
        norm_text,
        "## Reference bundle (the only context you have — no tools, read nothing else)",
        context_bundle,
    ]
    if resolutions:
        sections.append(
            "## Answers to your open critiques from a previous pass\n\n"
            + "\n\n".join(
                f"Q: {r['critique_question']}\nA: {r['answer']}" for r in resolutions
            )
            + "\n\nProduce your FINAL, complete test file and requirements JSON now, "
              "incorporating these resolutions — update each affected requirement's "
              "clarity_resolution field and adjust your tests to actually assert the "
              "resolved behavior where it matters. Any remaining open_critiques must be "
              "genuinely new ones these answers didn't already cover."
        )
    else:
        sections.append(
            "Design every requirement and write your test file and requirements JSON now, "
            "following your standing instructions."
        )
    return "\n\n".join(sections)


def call_norm_architect_agent(round_number, norm_text, context_bundle, resolutions=None):
    """Returns the raw response text on success, or None after exhausting
    MAX_ARCHITECT_ATTEMPTS — the caller (engine.simulate) is responsible
    for extracting the ```python test file and ```json requirements block
    from that text; this function only owns the completion call itself,
    matching call_fisher_agent/call_critique_agent's own division of
    labor. `resolutions`, when given, is a list of {"critique_question",
    "answer"} dicts from a previous pass's open_critiques, folded into a
    second, finalizing call."""
    user_prompt = _build_norm_architect_prompt(round_number, norm_text, context_bundle, resolutions)
    model_spec = (
        os.environ.get("NORM_ARCHITECT_MODEL")
        or os.environ.get("NORM_IMPLEMENTER_MODEL")  # transition fallback, pre-split env var
        or os.environ.get("OPENCODE_MODEL")
        or DEFAULT_FISHER_MODEL
    )
    completion_kwargs = _resolve_completion_kwargs(model_spec)

    last_error = None
    for attempt in range(1, MAX_ARCHITECT_ATTEMPTS + 1):
        start = time.monotonic()
        raw_text = ""
        error = None
        try:
            response = litellm.completion(
                messages=[
                    {"role": "system", "content": NORM_ARCHITECT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=1800,
                **completion_kwargs,
            )
            raw_text = response.choices[0].message.content or ""
        except Exception as exc:
            error = str(exc)
        duration_s = time.monotonic() - start

        log_call(
            also_log_to=NORM_ARCHITECT_LOG_PATH,
            call="norm_architect",
            agent_id=None,
            round=round_number,
            action=None,
            model=model_spec,
            attempt=attempt,
            duration_s=round(duration_s, 3),
            returncode=0 if error is None else 1,
            prompt=user_prompt,
            raw_response=raw_text,
            parsed_response=None,
            error=error if error else (None if raw_text.strip() else "empty response"),
        )

        if not error and raw_text.strip():
            return raw_text
        last_error = error or "empty response"
        print(f"  [norm-architect round {round_number} attempt {attempt}/{MAX_ARCHITECT_ATTEMPTS} "
              f"failed: {last_error} — retrying]")
        if attempt < MAX_ARCHITECT_ATTEMPTS:
            time.sleep(ARCHITECT_CALL_DELAY_S)

    print(f"Round {round_number}: norm-architect call failed after {MAX_ARCHITECT_ATTEMPTS} "
          f"attempts: {last_error}", file=sys.stderr)
    return None


NORM_AUDITOR_LOG_PATH = ROOT / "ops" / "logs" / "norm_auditor.jsonl"
MAX_AUDITOR_ATTEMPTS = 3
AUDITOR_CALL_DELAY_S = float(os.environ.get("LLM_CALL_DELAY_S", "2"))

# 2026-09-23: norm-auditor moved to the same no-tools direct-completion
# shape as norm-architect (see call_norm_architect_agent()'s own
# docstring for the root cause — DeepSeek-R1 doesn't support tool calling
# on Ollama). It never actually needed real tools either: its job is
# reading two fixed texts (the raw norm and the round's diff) and judging
# whether the second one actually satisfies the first — a plain
# completion call does that exactly as well as an opencode agent with
# read/glob/grep/bash tools did, without the "does not support tools" 400
# and without the extra latency of a real agentic session. By request,
# this also drops the earlier design's requirement that the auditor write
# its OWN independent pytest suite (tests/norm_evaluation/round_N/) —
# a direct text-level cross-reference of norm vs. code, the same
# "Software Regulatory Compliance Auditor" framing requested, catches the
# exact failure class that mattered (a norm-engineer that wrote
# syntactically fine code and even passing tests that are themselves
# quietly wrong — e.g. flipping a >10%-over-quota / else-$1,000 threshold
# into a flat $5,000 fine) without needing the auditor to independently
# reimplement test-writing on top of that.
NORM_AUDITOR_SYSTEM_PROMPT = """You are a strict Software Regulatory Compliance Auditor for a multi-agent
fishery simulation. Your job is to cross-reference a completed code
change against the original fishery norm document it's supposed to
implement, and find logical gaps, omissions, or errors — including ones
that still compile cleanly and pass their own tests. You have NO TOOLS
and no filesystem access beyond what's in this message: you cannot read
another file, run the tests yourself, or check anything not given to you
here.

You are auditing, not implementing: never suggest new normative content
the norm's own text doesn't already entail, never edit anything, never
approve code because it merely runs without crashing.

The single most important failure class to hunt for is UNDER-ENFORCEMENT
— code that is technically present, compiles, and even has a test that
passes, but implements the norm's own requirement more weakly or crudely
than its text demands. Two concrete examples of exactly this:
- The norm requires a 48-hour cooldown period for a violation; the code
  only sets a boolean flag (`has_violated: true`) with no timestamp or
  duration check at all — every test asserting "the flag gets set" would
  pass, while the actual 48-hour requirement is completely unenforced.
- The norm says "fine a boat $5,000 if it exceeds its monthly quota by
  more than 10%, or $1,000 if it exceeds it by 10% or less"; the code
  applies a flat $5,000 fine regardless of the actual overage percentage,
  or miscalculates the 10% threshold itself (off-by-one, wrong base
  quantity, inverted comparison).
Look specifically for a norm clause containing a duration, a threshold, a
rate, a count, or a conditional (if/else) split, and check whether the
code's own conditional logic and magnitudes actually match — not just
whether *a* consequence fires.

## Output format

Write your analysis of what you checked and what you found. Then, as the
LAST thing in your response, on its own line:
- If the code fully and correctly implements everything the norm
  document requires, with no under-enforcement, output exactly:
  AUDIT_PASSED
- If you find any gap, omission, or under-enforcement, do NOT output that
  phrase — instead end with a clear, specific description of exactly
  what rule was violated or missed, quoting both the norm's own text and
  the code's actual (wrong) behavior, precise enough that a developer
  could fix it from your description alone."""


def _build_norm_auditor_prompt(round_number, norm_text, diff_text):
    return (
        f"This is round {round_number}. Audit norm-engineer's completed changes below.\n\n"
        f"## [ORIGINAL FISHERY NORM DOCUMENT] (norm.txt)\n\n{norm_text}\n\n"
        f"## [GENERATED CODE IMPLEMENTATION] (this round's diff)\n\n"
        f"```diff\n{diff_text}\n```\n\n"
        f"Cross-reference the code against the norm. Did the developer miss any subtle edge "
        f"case, exemption, or conditional calculation explicitly demanded by the norm? "
        f"Follow your standing instructions and output format."
    )


def call_norm_auditor_agent(round_number, norm_text, diff_text):
    """Returns the raw response text on success, or None after exhausting
    MAX_AUDITOR_ATTEMPTS. The caller (engine.simulate) checks the response
    for the literal AUDIT_PASSED sentinel; this function only owns the
    completion call itself, matching call_norm_architect_agent's own
    division of labor. Always a fresh, independent call — never reuses
    any session/context the code-writing model touched, which is the
    actual mechanism behind "never let the model that wrote the code
    approve its own work" (a NORM_AUDITOR_MODEL pointed at the same
    weights as NORM_ARCHITECT_MODEL is fine; what matters is that this
    call never sees norm-engineer's own reasoning, only its final diff)."""
    user_prompt = _build_norm_auditor_prompt(round_number, norm_text, diff_text)
    model_spec = (
        os.environ.get("NORM_AUDITOR_MODEL")
        or os.environ.get("NORM_IMPLEMENTER_MODEL")  # transition fallback, pre-split env var
        or os.environ.get("OPENCODE_MODEL")
        or DEFAULT_FISHER_MODEL
    )
    completion_kwargs = _resolve_completion_kwargs(model_spec)

    last_error = None
    for attempt in range(1, MAX_AUDITOR_ATTEMPTS + 1):
        start = time.monotonic()
        raw_text = ""
        error = None
        try:
            response = litellm.completion(
                messages=[
                    {"role": "system", "content": NORM_AUDITOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=1800,
                **completion_kwargs,
            )
            raw_text = response.choices[0].message.content or ""
        except Exception as exc:
            error = str(exc)
        duration_s = time.monotonic() - start

        log_call(
            also_log_to=NORM_AUDITOR_LOG_PATH,
            call="norm_auditor",
            agent_id=None,
            round=round_number,
            action=None,
            model=model_spec,
            attempt=attempt,
            duration_s=round(duration_s, 3),
            returncode=0 if error is None else 1,
            prompt=user_prompt,
            raw_response=raw_text,
            parsed_response=None,
            error=error if error else (None if raw_text.strip() else "empty response"),
        )

        if not error and raw_text.strip():
            return raw_text
        last_error = error or "empty response"
        print(f"  [norm-auditor round {round_number} attempt {attempt}/{MAX_AUDITOR_ATTEMPTS} "
              f"failed: {last_error} — retrying]")
        if attempt < MAX_AUDITOR_ATTEMPTS:
            time.sleep(AUDITOR_CALL_DELAY_S)

    print(f"Round {round_number}: norm-auditor call failed after {MAX_AUDITOR_ATTEMPTS} "
          f"attempts: {last_error}", file=sys.stderr)
    return None
