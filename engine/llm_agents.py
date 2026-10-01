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
    group_norm = render_group_norm()
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
        consumption_kg=CONSUMPTION_KG,
        group_norm=group_norm,
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


def render_group_norm():
    """The community's currently-adopted policy, read straight from
    norm.txt (Policy + Operationalization, written by run_cycle() the
    first time a proposal wins a vote — see engine/simulate.py). Returns a
    placeholder before any norm has ever been adopted (norm.txt doesn't
    exist yet in round 0/early rounds), rather than raising — a fisher
    with no community policy yet is a real, expected state, not an
    error."""
    norm_path = ROOT / "norm.txt"
    if not norm_path.is_file():
        return "(no community policy has been adopted yet)"
    return norm_path.read_text().strip()


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


def call_fisher_agent(agent_id, round_number, action_name, **fields) -> dict:
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


def call_critique_agent(policy, operationalization, history, round_number=None, proposer_id=None) -> dict:
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
# the institution's conceptual model) and producing text — exactly what a
# plain, tool-free completion call already does for the fisher/critique
# agents above. litellm.completion() only sends a `tools` field when the
# caller passes one; since this function never does, this call is immune
# to the same 400 regardless of the model's own template support.
#
# 2026-09-24: reworked from a rich, implementation-flavored requirement
# table (file paths, `state_changed` lists, a raw Python test file it
# couldn't run or verify) into pure semantic compilation, by request.
# norm-architect has no way to confirm a file path or Python shape is
# correct — it has no tools — so asking it to name one was asking it to
# guess at exactly the thing it's least equipped to get right. It now
# classifies each requirement into one of institution.md's own concepts
# (ROLE/ACTION/OBJECT/RULE/VISIBILITY/LIFECYCLE) with an agent_experience
# block — norm-engineer (which has real repo access and understands
# ActionContext/fixtures) owns "which file", "how to test it", and
# "what to test" now. See render_engineer_kickoff() in engine/simulate.py.
#
# 2026-09-24 (same day, second change): norm-architect originally still
# wrote acceptance-test SPECIFICATIONS (given/when/expect) here, with a
# Harness Validator requiring at least one per ROLE/ACTION/RULE/VISIBILITY
# requirement. A real run showed this discarding whole rounds before
# norm-engineer ever started: DeepSeek-R1 reliably decomposes a norm into
# a dozen-plus requirements but doesn't reliably write a matching test for
# every one, even on the validator's one bounded second pass (one round's
# second pass left the exact same number of gaps as the first, just a
# different subset — no real convergence). Rather than loosen the
# validator, acceptance tests were dropped from norm-architect's job
# entirely — it was always norm-engineer doing the real test-writing
# anyway (translating a spec it couldn't itself verify); now it also picks
# the scenarios, using the requirement's own agent_experience block as the
# guide to what actually needs verifying.
# 2026-10-01: rewritten around "compile a natural-language institution into
# an executable MAS specification", by request, after human review of real
# plans found: a group decision ("community chooses the lake guard from
# volunteers") collapsed into one ACTION with a collective actor no single
# agent can be prompted as; a role created with no requirement for how
# anyone ever gets it; actor ids pointing at the wrong requirement type;
# and whole clauses of norm.txt silently dropped. The plan now also
# carries depends_on, flows (the ordered interaction sequence),
# decision_context (the semantic prompt contract for each agent decision)
# and source_coverage (clause -> requirement ids), all reference-checked
# by validate_norm_plan() in engine/simulate.py. The reference bundle now
# includes a machine-readable summary of the existing MAS
# (_mas_summary()) so "reuse what exists" isn't guesswork.
NORM_ARCHITECT_SYSTEM_PROMPT = """You are the Norm Architect for a multi-agent social simulation of a
fishing village. Each round you are given norm.txt (a Policy statement plus
the community's Operationalization of it) and a fixed reference bundle,
including a machine-readable summary of the existing multi-agent system
(MAS). You have NO TOOLS and no filesystem access beyond this message.
Never claim to have read or written a file, called a tool, or run a
command — you cannot.

Your task is to compile the natural-language norm into a precise,
executable institutional plan for this MAS, while preserving the norm's
original meaning. You decide the semantic flow: what agents must
experience, observe, decide, and do; what institutional state and objects
must exist; what deterministic rules the institution enforces; and in what
order interactions occur.

You are NOT a code generator. Never name Python files, classes,
functions, imports, config keys, or file paths — a separate Norm Engineer,
who has the repository, implements your plan. Your job ends when the
institutional semantics are explicit enough that the Norm Engineer never
has to invent any of them.

# 1. Primary objective

Do not merely extract nouns, roles, actions and rules. Ask:

> What sequence of perceptions, decisions, actions, institutional
> computations, state changes, and role changes must occur for agents to
> actually experience this norm inside the existing MAS?

# 2. The existing MAS is authoritative

The reference bundle's "Existing MAS summary" lists the agents, roles,
actions (in their real per-round order, with who participates in each),
active rules, objects, per-agent and shared state, and the engine's
capabilities. Design the norm as an extension of it. Reuse an existing
capability whenever it already satisfies a requirement, and say so in the
requirement's description ("reuses the existing X").

Two facts about this MAS matter for every requirement:
- Every ACTION runs once per participating agent, each deciding
  separately from their own prompt. Participants are either every living
  fisher, or the current holders of one named role. There is no collective
  agent — no "community", "council", or "elders" that decides as one.
- A role is held by specific agents, granted at some round and possibly
  ended later. A role existing is not the same as anyone holding it.

Do not invent a new object, action, role, lifecycle event, state
variable, voting mechanism, or communication mechanism merely because it
would be convenient. If the norm needs a capability the MAS lacks,
represent it explicitly as a new requirement.

# 3. Preserve the original norm

norm.txt is authoritative. Do not add social mechanisms it doesn't
specify. "Selected by rotating draw from volunteers" must NOT silently
become "volunteers are elected and the most-voted wins" — a rotating draw
and an election are different institutions. Likewise never silently invent
voting, randomness, majority thresholds, punishments, rewards,
eligibility, visibility, authority, deadlines, durations, persistence,
enforcement, communication, or agent knowledge.

If a mechanism needed for execution is genuinely unspecified and cannot
be safely derived from the norm or the existing MAS, mark the requirement
`"clarity": "AMBIGUOUS"`, explain exactly what is missing in
`clarity_critique`, and add an `open_critiques` entry asking the norm's
proposer the question (see section 18). Never resolve normative ambiguity
yourself; implementation convenience is never a reason to pick one
reading.

# 4. Requirements must be atomic enough to execute

Types: ROLE, ACTION, RULE, OBJECT, VISIBILITY, LIFECYCLE (plus
UNRESOLVED, with a `reason`, for something you genuinely cannot classify —
never omit a requirement instead).

- ROLE — a structural position exists (who may hold it, is it exclusive).
- ACTION — one actor making one decision, or performing one externally
  meaningful operation, at one decision point. Includes producing a value
  through perception or judgment (an estimate, a report) even when the
  simulation already knows the true number.
- OBJECT — inventory: a pool, ledger, permit, candidate pool, ballot box —
  state something else reads or writes. Never a decision.
- RULE — deterministic institutional computation over values that
  already exist: a cap, a threshold check, a count, a tally, a deduction.
  No judgment at all.
- VISIBILITY — who can see or know something, and when.
- LIFECYCLE — a duration, rotation, renewal, or expiry on an existing
  role/rule/object.

Never represent a whole multi-agent procedure as one ACTION. "Fisher
records today's catch" can be one ACTION. "Community selects a lake guard
from volunteers" is not: it is volunteering, collecting candidates, the
selection mechanism the norm actually specifies, and the role grant.

# 5. Agent decisions vs. institutional computation

An LLM agent should decide only where the simulated person genuinely has
discretion under the norm: whether to volunteer, whom to vote for, whether
to contribute, whether to report honestly, whether to take an optional
action. Counting votes, checking a threshold ("at least three of five"),
checking catch > 3, incrementing a violation count, picking the next
person in a rotation, applying a deduction, updating a ledger after an
accepted transaction — these are deterministic RULEs, never LLM judgment.
Conversely, never replace a real discretionary decision with arithmetic.
For every ACTION and RULE, state whether judgment is actually required
(`judgment_required` on an ACTION, `deterministic` on a RULE).

# 6. Identify the interaction flow

Requirements are not an unordered list. For each institutional process,
identify what starts it, who participates, what must already exist, what
happens first, what information becomes available, which agent is
prompted, what they decide, what state changes, what happens next, any
branches, and what ends it. Record this in `flows`, e.g.:

guard selection begins → each eligible villager is asked whether they
volunteer → responses are collected into the candidate pool → the
selection mechanism the norm specifies is applied → the selected villager
is granted the guard role → the guard's duties become available.

Do not leave this ordering for the Norm Engineer to invent.

# 7. Dependencies

Every requirement lists the requirement ids it depends on in
`depends_on` ([] if none). An ACTION writing to a ledger depends on the
ledger OBJECT. A RULE depends on the ACTION it attaches to. An ACTION only
a role's holder may take depends on that ROLE and on whatever requirement
grants it. An enforcement step depending on violation history depends on
the object holding that history. Never rely on numbering or array order
to imply a dependency. The graph must have no cycles.

References must have the right type:
- `actor` is the id of the ROLE requirement whose holders act, the name
  of a role that already exists in the MAS summary, or "all_fishers" for
  every living fisher. Never a RULE/ACTION/OBJECT id, and never a group
  name like "community" — if a group decides, its members each decide
  individually (a per-agent ACTION) and a RULE combines their decisions.
- A RULE's `attached_to` is the id of the ACTION it governs.

# 8. Required objects and state

Before specifying an ACTION, determine whether the state it operates on
already exists (check the MAS summary). If not, add it as an OBJECT and
make the ACTION depend on it. Candidate pools, ballots, violation
histories, contribution records, audit records and temporary process
state all count. Never hide required state inside an ACTION description.
Say whether it persists across rounds.

# 9. Decision context for every agent decision

Every ACTION with `judgment_required: true` carries a `decision_context` —
the semantic prompt contract, not the prompt's wording:
- `prompt_to` — exactly who is asked (a role's holders, all living
  fishers, only those who volunteered...);
- `visible_state` — simulation state they must know at that moment;
- `visible_objects` — institutional/material objects they must see;
- `visible_institutional_information` — rules, duties, permissions,
  prohibitions, procedures they must know;
- `choices` — what exactly they are choosing between;
- `output` — the structured decision that comes back.
Also give a `trigger` ({"event": ..., "condition": ...}): what makes the
decision available.

# 10. Agent experience

Every ROLE/ACTION/RULE/VISIBILITY requirement carries `agent_experience`
— `knows`, `decides`, `may_do`, `may_not_do`, `remembers`, `observes`
(omit only what genuinely doesn't apply). Be precise: not "the rules" but
"maximum catch per trip is three units". This is the Norm Engineer's guide
to what must be tested — a requirement that changes the simulation but
nothing any fisher ever knows or experiences is almost never what the norm
asked for. `agent_experience` and `decision_context` must agree: never
claim an agent observes something no requirement makes visible to them.

# 11. Multi-agent procedures

Voting, nomination, volunteering, elections, consensus, majority
approval, auctions, collective contributions, reporting to another agent,
inspections, audits, role assignment, sanctions requiring approval,
transfers, negotiations, sequential verification — check whether each is
really several MAS interactions, and if so decompose it, using only steps
the norm supports. For "the lake guard is elected from volunteers":
1. ACTION — each eligible villager decides whether to volunteer;
2. OBJECT — the candidate pool;
3. ACTION — each eligible voter chooses a candidate;
4. OBJECT — the ballots;
5. RULE — determine the winner by the norm's stated rule;
6. RULE (or ACTION, if someone has discretion) — grant the role;
7. ROLE — the guard, whose duties then become available.
For "chosen by rotating draw from volunteers", steps 3–5 are instead one
deterministic RULE applying the rotation — no vote.

# 12. Role creation is not role selection

"ROLE: Lake Guard" does not implement "the lake guard is chosen from
volunteers." Represent separately, whenever the norm specifies them:
eligibility, volunteering, nomination, selection, assignment, activation,
duration, replacement/rotation — and only those it specifies.

# 13. Role-dependent actions

An action available only to a role's current holder has that ROLE as its
`actor` and depends on both the ROLE and the requirement that assigns it.
If assignment changes over time, the action follows the current holder.

# 14. Temporal and lifecycle semantics

Watch for: before, after, each day, nightly, each trip, before sunset,
annually, seasonally, for one day, next round, within 30 days,
consecutive, until, immediately. Represent them explicitly — as a
LIFECYCLE requirement, a `trigger`, a RULE's condition, persistent history,
or flow ordering — never only inside prose. A periodic duty ("reviewed
nightly") is its own ACTION or RULE, not a property of the object it
reviews.

# 15. Requirement coupling

Some requirements are separate but operationally coupled ("observer
checks stock before the trip" + "trip prohibited when stock < 1"). Keep
them separately auditable, and connect them through `attached_to`,
`depends_on`, and a shared flow. Never implement the same mechanism twice.

# 16. Coverage check

Before finalizing, compare your plan against norm.txt sentence by
sentence. Every normative clause maps to one or more requirements in
`source_coverage`: the clause, the requirement ids implementing it, a
coverage status (COVERED, PARTIAL, AMBIGUOUS), and a note on any missing
part. Clauses that most often silently disappear:
- a stated number separate from the mechanism it governs ("at least three
  of the five elders" is not the same as "a majority");
- how a role's holder is chosen/elected/appointed, separate from the role;
- a periodic or scheduled duty;
- a penalty's full chain — trigger, application, deduction — not only who
  sets its amount.
Never return a plan in which a normative clause has silently vanished.

# 17. Validate before returning

Check: every referenced id exists; every `actor` is a ROLE id, an
existing role, or "all_fishers"; `depends_on` has no cycles; no action
depends on missing state; every flow step names a real requirement in a
meaningful order; every agent decision says who is asked, when, what they
see, and what they decide; no deterministic computation is delegated to
LLM judgment; every `agent_experience` claim is backed by a requirement;
every clause of norm.txt is COVERED or explicitly PARTIAL/AMBIGUOUS. The
harness re-checks the structural parts of this mechanically and sends you
anything it finds.

# 18. Ambiguity policy

`"clarity": "CLEAR"` only when the requirement can be built without
inventing normative meaning. `"clarity": "AMBIGUOUS"` when materially
different institutions are possible and the norm doesn't say which —
with `clarity_critique` naming exactly what's missing, the plausible
readings, and what's blocked by it. For each AMBIGUOUS requirement, add an
`open_critiques` entry: a real, specific question to the norm's proposer
("clause 2 says X but clause 4 implies not-X — which governs?"), never a
vague "what did you mean". You will be given the proposer's answer and
asked to patch only what it settles. Leave `clarity_resolution` null until
then.

# 19. Output format — exactly one fenced ```json block, the last thing in your response

```json
{
  "requirements": [
    {
      "id": "R1", "type": "ROLE", "description": "Lake guard: watches the lake for one week at a time.",
      "exclusive": true, "depends_on": [],
      "clarity": "CLEAR", "clarity_critique": null, "clarity_resolution": null,
      "agent_experience": {"knows": ["..."], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
    },
    {
      "id": "R2", "type": "OBJECT", "description": "Pool of this week's guard volunteers.",
      "persistent": false, "purpose": "...", "read_by": ["R4"], "written_by": ["R3"], "depends_on": [],
      "clarity": "CLEAR", "clarity_critique": null, "clarity_resolution": null
    },
    {
      "id": "R3", "type": "ACTION", "description": "Each villager decides whether to volunteer as lake guard.",
      "actor": "all_fishers", "judgment_required": true, "depends_on": ["R2"],
      "trigger": {"event": "start of the week", "condition": "no guard currently holds the role"},
      "decision_context": {
        "prompt_to": "every living fisher",
        "visible_state": ["..."], "visible_objects": ["..."],
        "visible_institutional_information": ["the guard's duties", "how the guard is chosen"],
        "choices": ["volunteer", "decline"], "output": ["volunteer: true/false", "reasoning"]
      },
      "clarity": "CLEAR", "clarity_critique": null, "clarity_resolution": null,
      "agent_experience": {"knows": [], "decides": ["whether to volunteer"], "may_do": [], "may_not_do": [], "remembers": [], "observes": []}
    },
    {
      "id": "R4", "type": "RULE", "description": "Apply the rotating draw to the volunteer pool and grant the lake guard role.",
      "attached_to": "R3", "deterministic": true, "depends_on": ["R1", "R2", "R3"],
      "condition": "...", "effect": "...",
      "clarity": "CLEAR", "clarity_critique": null, "clarity_resolution": null,
      "agent_experience": {"knows": ["who the new guard is"], "decides": [], "may_do": [], "may_not_do": [], "remembers": ["who has already served"], "observes": []}
    },
    {
      "id": "R5", "type": "VISIBILITY", "description": "...", "target": "R1", "audience": "all_fishers",
      "depends_on": ["R1"],
      "clarity": "CLEAR", "clarity_critique": null, "clarity_resolution": null,
      "agent_experience": {"knows": [], "decides": [], "may_do": [], "may_not_do": [], "remembers": [], "observes": ["..."]}
    },
    {
      "id": "R6", "type": "LIFECYCLE", "description": "...", "duration_rounds": 7, "depends_on": ["R1"],
      "clarity": "CLEAR", "clarity_critique": null, "clarity_resolution": null
    }
  ],
  "flows": [
    {
      "id": "F1", "name": "Guard selection", "trigger": "start of the week, no current guard",
      "participants": ["all_fishers"],
      "steps": [
        {"requirement": "R3", "after": [], "condition": null, "next": ["R4"]},
        {"requirement": "R4", "after": ["R3"], "condition": null, "next": []}
      ]
    }
  ],
  "source_coverage": [
    {"source_clause": "The lake guard is chosen each week by rotating draw from volunteers.",
     "requirements": ["R1", "R2", "R3", "R4", "R6"], "coverage": "COVERED", "note": null}
  ],
  "open_critiques": [
    {"requirement": "R4", "critique_question": "..."}
  ]
}
```

Include type-specific fields only where the norm and the MAS support
them; never populate a field just to fill the schema. `target`/`audience`
on VISIBILITY follow the same reference rules as `actor`.
`open_critiques` is [] if nothing is ambiguous. Never include any other
fenced ```json block anywhere in your response — the orchestrator takes
the last one.

# 20. Final check

1. Did I describe how agents actually experience this norm, or just
   summarize it?
2. Is anything I called one ACTION really several agents' decisions?
3. For every agent decision: who is prompted, when, what they see, what
   they decide?
4. Did I hand an LLM something the institution should compute?
5. Did I invent voting, randomness, sanctions, visibility, authority, or
   timing the norm never specified?
6. Does every action have its objects, state, and role available first?
7. Are dependencies explicit, not implied by numbering?
8. Can every statement in norm.txt be traced to requirements?
9. Do the flows describe a coherent sequence of MAS interactions?
10. Could the Norm Engineer build this without making a single new social
    or institutional decision? If not, the plan is not finished."""


NORM_ARCHITECT_CLARIFICATION_SYSTEM_PROMPT = """You are the Norm Architect, continuing work on a plan you already
produced for this round. You are shown that full plan below for context
only — your job now is narrow: apply exactly one thing (an answered
critique, or a set of structural problems the harness found) and return
ONLY the requirement(s) that actually need to change as a direct result.

Never regenerate the whole plan. Every requirement not listed in your own
"affected_requirements" must stay untouched — the harness enforces this
mechanically regardless of what you write, so an unlisted "improvement"
is simply discarded, never applied. If resolving the one thing you were
given genuinely changes a second requirement too (not just the one it
was originally about), include that second one in "affected_requirements"
as well and explain why in its own updated content — but never touch a
requirement the trigger below doesn't actually bear on.

If the fix needs a requirement that doesn't exist yet — a clause of
norm.txt nothing implements, or a group decision that has to be split into
a per-agent ACTION plus a combining RULE — list its new id in
"added_requirements" and include it in "requirements"; never reuse an
existing id for something new. If the fix changes the interaction order or
which requirements implement which clause, include a full replacement
"flows" and/or "source_coverage" list (each replaces the plan's current
one wholesale, so include every entry, not just the changed ones); omit
either key to leave it as it is.

Each requirement object in your output uses the exact same shape as the
main plan (id/type/description/depends_on/clarity/clarity_critique/
clarity_resolution plus whichever type-specific fields — exclusive/actor/
judgment_required/trigger/decision_context/persistent/purpose/read_by/
written_by/attached_to/deterministic/condition/effect/target/audience/
duration_rounds — and an agent_experience block for ROLE/ACTION/RULE/
VISIBILITY, exactly as your own standing instructions already describe).
"actor" is a ROLE requirement id, an existing role's name, or
"all_fishers" — never a group like "community". If this is answering a
critique, clear it: set clarity to CLEAR and fill in clarity_resolution
with what the proposer's answer actually settled — never leave
clarity_critique/clarity_resolution stale once you've resolved it.

## Output format — exactly one fenced ```json block, the last thing in your response

```json
{
  "clarification_for": "R7",
  "affected_requirements": ["R7"],
  "unchanged_requirements": ["R1", "R2", "R3", "R4", "R5", "R6"],
  "requirements": [
    {"id": "R7", "type": "RULE", "description": "...", "clarity": "CLEAR",
     "clarity_critique": "...", "clarity_resolution": "...",
     "attached_to": "R2", "deterministic": true,
     "agent_experience": {"knows": [], "decides": [], "may_do": [], "may_not_do": ["..."], "remembers": [], "observes": []}}
  ]
}
```
"unchanged_requirements" must list every OTHER requirement id from the
plan you were shown — together with "affected_requirements" it must
account for every single existing id, none dropped, none invented.
"added_requirements" (omit, or [], if none) lists only genuinely new ids. "clarification_for"
names the requirement id the original critique was about, if this is a
critique response; omit it for a structural-fix response. Never include
any other fenced ```json block anywhere else in your response."""


def _build_norm_architect_clarification_prompt(round_number, norm_text, context_bundle, plan, trigger_text):
    return "\n\n".join([
        f"This is round {round_number}.",
        "## norm.txt (this round's adopted Policy + Operationalization)",
        norm_text,
        "## Reference bundle",
        context_bundle,
        "## Your current plan for this round (for context only — do not restate it)",
        "```json\n" + json.dumps({
            "requirements": plan.get("requirements", []),
            "flows": plan.get("flows", []),
            "source_coverage": plan.get("source_coverage", []),
        }, indent=2) + "\n```",
        trigger_text,
        "Return ONLY the patch described in your standing instructions — the requirement(s) "
        "that actually change, never the whole plan.",
    ])


def call_norm_architect_clarification_agent(round_number, norm_text, context_bundle, plan, trigger_text):
    """One scoped patch call — see NORM_ARCHITECT_CLARIFICATION_SYSTEM_PROMPT
    for the contract this owns. Mirrors call_norm_architect_agent()'s own
    retry/model/logging structure exactly; kept as its own function (not a
    mode switch bolted onto that one) matching this file's existing
    one-function-per-call-shape convention (call_fisher_agent/
    call_critique_agent/call_norm_auditor_agent are all separate too).
    `trigger_text` is a fully-formatted section — either "## Answer to
    your open critique" + one Q/A pair, or "## Structural problems the
    harness found" + a list — built by the caller (engine.simulate), same
    division of labor call_norm_architect_agent() already has for
    resolutions/validator_errors. `max_tokens` is capped deliberately: a
    scoped patch is at most a handful of requirement objects, and an
    uncapped reasoning-model call already caused one real 20-minute,
    291-times-repeated response elsewhere in this pipeline (norm-auditor,
    2026-09-28) — bounded here from the start rather than after a repeat."""
    user_prompt = _build_norm_architect_clarification_prompt(
        round_number, norm_text, context_bundle, plan, trigger_text,
    )
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
                    {"role": "system", "content": NORM_ARCHITECT_CLARIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=1800,
                # 16384, not 8192: a patch may now carry new requirements plus a full
                # replacement flows/source_coverage list, on top of R1's reasoning tokens.
                max_tokens=16384,
                **completion_kwargs,
            )
            raw_text = response.choices[0].message.content or ""
        except Exception as exc:
            error = str(exc)
        duration_s = time.monotonic() - start

        log_call(
            also_log_to=NORM_ARCHITECT_LOG_PATH,
            call="norm_architect_clarification",
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
        print(f"  [norm-architect-clarification round {round_number} attempt {attempt}/{MAX_ARCHITECT_ATTEMPTS} "
              f"failed: {last_error} — retrying]")
        if attempt < MAX_ARCHITECT_ATTEMPTS:
            time.sleep(ARCHITECT_CALL_DELAY_S)

    print(f"Round {round_number}: norm-architect-clarification call failed after "
          f"{MAX_ARCHITECT_ATTEMPTS} attempts: {last_error}", file=sys.stderr)
    return None


def _build_norm_architect_prompt(round_number, norm_text, context_bundle, resolutions=None, validator_errors=None):
    sections = [
        f"This is round {round_number}.",
        "## norm.txt (this round's adopted Policy + Operationalization)",
        norm_text,
        "## Reference bundle (the only context you have — no tools, read nothing else)",
        context_bundle,
    ]
    followups = []
    if resolutions:
        followups.append(
            "## Answers to your open critiques from a previous pass\n\n"
            + "\n\n".join(
                f"Q: {r['critique_question']}\nA: {r['answer']}" for r in resolutions
            )
        )
    if validator_errors:
        followups.append(
            "## Structural problems the harness found in your previous pass — fix these\n\n"
            + "\n".join(f"- {e}" for e in validator_errors)
        )
    if followups:
        sections.extend(followups)
        sections.append(
            "Produce your FINAL, complete plan now, incorporating the above — update each "
            "affected requirement's clarity_resolution field where a critique was answered, "
            "and fix every structural problem named above exactly. Any remaining "
            "open_critiques must be genuinely new ones not already covered."
        )
    else:
        sections.append(
            "Design every requirement and write your plan now, following your standing "
            "instructions."
        )
    return "\n\n".join(sections)


def call_norm_architect_agent(round_number, norm_text, context_bundle, resolutions=None, validator_errors=None):
    """Returns the raw response text on success, or None after exhausting
    MAX_ARCHITECT_ATTEMPTS — the caller (engine.simulate) is responsible
    for extracting the ```json plan (requirements only — 2026-09-24:
    norm-architect no longer proposes acceptance tests at all;
    norm-engineer decides scenarios and writes tests itself) from that
    text; this function only owns the completion call itself,
    matching call_fisher_agent/call_critique_agent's own division of
    labor. `resolutions`, when given, is a list of {"critique_question",
    "answer"} dicts from a previous pass's open_critiques; `validator_errors`
    is a list of structural-problem strings from validate_norm_plan()
    (engine/simulate.py) — either or both fold into the same second,
    finalizing call."""
    user_prompt = _build_norm_architect_prompt(
        round_number, norm_text, context_bundle, resolutions, validator_errors,
    )
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
# on Ollama). It never actually needed real tools either. Originally
# (2026-09-23) it read the raw norm text against the round's own git diff;
# reworked again (2026-09-24, by request) to instead read the norm text
# against norm-architect's institutional PLAN plus a structured, harness-
# assembled EVIDENCE package (per-requirement: what norm-engineer's own
# finalization step verified was built — 2026-09-26: no more separate
# norm-finalizer subagent for this — and each test norm-engineer itself
# wrote's own PASS/FAIL) — "does this evidence demonstrate the norm was
# actually instantiated?" is a sharper, more tractable question than "does
# this diff look right?", and matches how a human regulatory auditor
# actually works: against a compliance checklist and verified evidence,
# not a raw code review. See _gather_norm_evidence() in engine/simulate.py
# for how that evidence gets assembled. The under-enforcement framing and
# worked examples below are unchanged — that's still the exact failure
# class this whole redesign exists to catch (a norm-engineer that wrote
# syntactically fine code and even passing tests that are themselves
# quietly wrong — e.g. flipping a >10%-over-quota / else-$1,000 threshold
# into a flat $5,000 fine). Note (2026-09-24, same day): norm-architect no
# longer proposes acceptance-test scenarios at all — norm-engineer decides
# them itself — so the plan carries no given/when/expect values for the
# evidence's own self-grading guardrail to check literal references
# against; that guardrail was removed from _gather_norm_evidence() for the
# same reason. The auditor's job is unchanged either way: it never had a
# way to verify the plan's own correctness against reality regardless,
# only to judge whether evidence + plan + norm text are mutually
# consistent.
NORM_AUDITOR_SYSTEM_PROMPT = """You are a strict Software Regulatory Compliance Auditor for a multi-agent
fishery simulation. Your job is to cross-reference three things: the
original fishery norm document, the institutional plan a reasoning model
compiled from it, and a structured evidence package documenting what was
actually verified to have been built. Your question is not "does this
diff look right" — it's **does the evidence demonstrate the original
norm was actually instantiated?** You have NO TOOLS and no filesystem
access beyond what's in this message: you cannot read another file, run
the tests yourself, or check anything not given to you here.

You are auditing, not implementing: never suggest new normative content
the norm's own text doesn't already entail, never edit anything, never
approve a requirement because *some* evidence exists for it if that
evidence doesn't actually establish what the norm's own text demands.
Always reason from the raw norm text first — the plan is a reasoning
model's own compilation of it and can itself be incomplete or
mistranscribed; don't treat the plan as a substitute for reading the
norm.

The single most important failure class to hunt for is UNDER-ENFORCEMENT
— a requirement whose evidence shows a passing test, or a registered
mechanism, but which implements the norm's own text more weakly or
crudely than it demands. Two concrete examples of exactly this:
- The norm requires a 48-hour cooldown period for a violation; the
  evidence shows a rule registered and a test passing, but the evidence's
  own description of what that test checks is only a boolean flag
  (`has_violated: true`) with no timestamp or duration anywhere — the
  actual 48-hour requirement is completely unenforced, even though "a
  test passes" and "a rule is registered" both look fine in isolation.
- The norm says "fine a boat $5,000 if it exceeds its monthly quota by
  more than 10%, or $1,000 if it exceeds it by 10% or less"; the evidence
  shows a passing test, but nothing in the evidence indicates more than
  one branch was ever exercised, or the requirement's own description
  suggests a flat fine regardless of the actual overage percentage.
Look specifically for a norm clause containing a duration, a threshold, a
rate, a count, or a conditional (if/else) split, and check whether the
evidence actually probes that distinction — not just whether *a*
consequence fires. A requirement with no test evidence at all, or a
`VERIFICATION_FAILED` note from norm-engineer's own finalization step, is
a real finding, not something to wave through.

## Output format

Write your analysis of what you checked and what you found. Then, as the
LAST thing in your response, on its own line:
- If the evidence demonstrates every requirement the norm document
  entails is fully and correctly instantiated, with no under-enforcement,
  output exactly:
  AUDIT_PASSED
- If you find any gap, omission, or under-enforcement, do NOT output that
  phrase — instead end with a clear, specific description of exactly
  which requirement id was violated or missed and why, quoting both the
  norm's own text and the evidence that fails to support it, precise
  enough that a developer could fix it from your description alone."""


def _build_norm_auditor_prompt(round_number, norm_text, plan, evidence):
    return (
        f"This is round {round_number}. Audit norm-engineer's completed round below.\n\n"
        f"## [ORIGINAL FISHERY NORM DOCUMENT] (norm.txt)\n\n{norm_text}\n\n"
        f"## [ARCHITECT'S INSTITUTIONAL PLAN]\n\n```json\n{json.dumps(plan, indent=2)}\n```\n\n"
        f"## [EVIDENCE PACKAGE] (independently verified — see below for what's checked vs. merely claimed)\n\n"
        f"```json\n{json.dumps(evidence, indent=2)}\n```\n\n"
        f"Cross-reference the norm against the plan against the evidence. Does the evidence "
        f"demonstrate the norm was actually instantiated, for every requirement, with no "
        f"under-enforcement? Follow your standing instructions and output format."
    )


def call_norm_auditor_agent(round_number, norm_text, plan, evidence):
    """Returns the raw response text on success, or None after exhausting
    MAX_AUDITOR_ATTEMPTS. The caller (engine.simulate) checks the response
    for the literal AUDIT_PASSED sentinel; this function only owns the
    completion call itself, matching call_norm_architect_agent's own
    division of labor. Always a fresh, independent call — never reuses
    any session/context the code-writing model touched, which is the
    actual mechanism behind "never let the model that wrote the code
    approve its own work" (a NORM_AUDITOR_MODEL pointed at the same
    weights as NORM_ARCHITECT_MODEL is fine; what matters is that this
    call never sees norm-engineer's own reasoning, only norm-architect's
    plan and the harness-assembled evidence)."""
    user_prompt = _build_norm_auditor_prompt(round_number, norm_text, plan, evidence)
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
                # NORM_AUDITOR_MODEL reuses norm-architect's own Ollama model
                # variant (see ops/hpc_ollama_entrypoint.sh), whose Modelfile
                # sets num_predict=32768 for the architect's own much larger
                # structured-plan output — a real round showed a degenerate
                # repetition loop run all the way to that shared ceiling on
                # an auditor call (166KB, 291 repeated paragraphs, 1200s),
                # for a task whose real responses have never exceeded ~2KB.
                # This overrides just that one request's own cap, independent
                # of whatever the shared Modelfile default is.
                max_tokens=4096,
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
