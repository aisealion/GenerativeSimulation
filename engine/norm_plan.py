"""Parsing, validation, and scoped patching for norm-architect's own
plan output — everything that inspects or merges the plan dict itself,
with no LLM call and no opencode session. Extracted from engine/simulate.py
(2026-10-02) to keep that file to orchestration; engine/simulate.py
re-exports the five names norm_architect.py (sic: engine/simulate.py)
actually calls — validate_norm_plan, _parse_architect_plan,
_apply_clarification_patch, _known_institution_roles,
_known_institution_actions — so existing call sites and tests are
unaffected by the move.

Not reachable from norm-engineer's own permission.edit (this file isn't
on its allowlist) — same footing as engine/simulate.py itself."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VALID_NORM_PLAN_REQUIREMENT_TYPES = {"ROLE", "ACTION", "OBJECT", "RULE", "VISIBILITY", "LIFECYCLE", "UNRESOLVED"}


def validate_norm_plan(plan, known_roles=None, known_actions=None, norm_text=None):
    """The deterministic Harness Validator, between norm-architect and
    norm-engineer: catches structural incompleteness (a missing field, a
    dangling reference) before an expensive opencode session starts.
    Returns a list of problem strings (empty if sound) — never judges
    whether the plan is semantically right, only whether it's complete
    enough to act on.

    (2026-09-24: used to also require an acceptance-test entry per
    requirement, back when norm-architect proposed scenarios itself —
    dropped after DeepSeek-R1 didn't reliably converge on covering every
    flagged gap; norm-engineer owns test-writing now.)"""
    errors = []
    requirements = plan.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        return ["\"requirements\" must be a non-empty list"]

    seen_ids = set()
    for i, req in enumerate(requirements):
        label = f"requirements[{i}]"
        req_id = req.get("id")
        if not req_id:
            errors.append(f"{label} has no \"id\"")
            continue
        label = f"requirement {req_id!r}"
        if req_id in seen_ids:
            errors.append(f"{label}: duplicate id — every requirement needs a unique id")
        seen_ids.add(req_id)

        req_type = req.get("type")
        if req_type not in VALID_NORM_PLAN_REQUIREMENT_TYPES:
            errors.append(
                f"{label}: \"type\" is {req_type!r}, must be one of "
                f"{sorted(VALID_NORM_PLAN_REQUIREMENT_TYPES)}"
            )
            continue
        if req_type == "UNRESOLVED":
            if not req.get("reason"):
                errors.append(f"{label}: type UNRESOLVED needs a \"reason\" field")
            continue
        if not req.get("description"):
            errors.append(f"{label}: missing \"description\"")

        if req_type in ("ROLE", "ACTION", "RULE", "VISIBILITY") and not req.get("agent_experience"):
            errors.append(
                f"{label}: type {req_type} needs an \"agent_experience\" block — what does a "
                f"fisher actually know/decide/may-do/may-not-do/remember/observe because of this?"
            )

    errors += _norm_plan_reference_errors(plan, requirements, known_roles, known_actions)
    errors += _norm_plan_clause_coverage_errors(plan, norm_text)

    for i, critique in enumerate(plan.get("open_critiques") or []):
        critique_req = critique.get("requirement")
        if critique_req and critique_req not in seen_ids:
            errors.append(
                f"open_critiques[{i}]: \"requirement\" {critique_req!r} doesn't match any requirement id"
            )
        if not critique.get("critique_question"):
            errors.append(f"open_critiques[{i}]: missing \"critique_question\"")

    return errors


# "actor" without a requirement id: every living fisher, or a role
# already in state/institution.json's catalog (known_roles). Anything
# else ("community", an undeclared role) is a collective this engine has
# no way to prompt — every ACTION runs once per participating individual.
NORM_PLAN_BUILTIN_ACTORS = {"all_fishers"}
NORM_PLAN_COVERAGE_VALUES = {"COVERED", "PARTIAL", "AMBIGUOUS"}


def _norm_plan_reference_errors(plan, requirements, known_roles=None, known_actions=None):
    """Cross-reference half of validate_norm_plan(): actor/attached_to/
    assigned_by/depends_on/flows/source_coverage must each point at
    something real, of the right kind, with no depends_on cycle."""
    errors = []
    known_roles = set(known_roles or ())
    id_to_type = {req.get("id"): req.get("type") for req in requirements if req.get("id")}
    valid_actors = NORM_PLAN_BUILTIN_ACTORS | known_roles

    for req in requirements:
        req_id = req.get("id")
        if not req_id:
            continue
        label = f"requirement {req_id!r}"
        req_type = req.get("type")

        actor = req.get("actor")
        if actor:
            if actor in id_to_type:
                if id_to_type[actor] != "ROLE":
                    errors.append(
                        f"{label}: \"actor\" is {actor!r}, which is a {id_to_type[actor]} "
                        f"requirement, not a ROLE — \"actor\" must name the requirement id of the "
                        f"role whose holder acts here, never a rule, action, or object"
                    )
            elif actor not in valid_actors:
                errors.append(
                    f"{label}: \"actor\" is {actor!r}, which is neither a ROLE requirement id in "
                    f"this plan, an existing role ({sorted(known_roles) or 'none yet'}), nor "
                    f"\"all_fishers\" — every ACTION is one decision made separately by each "
                    f"individual agent who holds a role (or by every living fisher). If a group "
                    f"(\"community\", \"council\", \"elders\") decides, decompose it: a ROLE for "
                    f"its members, a per-agent ACTION where each one decides, and a deterministic "
                    f"RULE that combines their decisions"
                )

        attached_to = req.get("attached_to")
        if req_type == "RULE" and attached_to:
            if attached_to in id_to_type:
                if id_to_type[attached_to] != "ACTION":
                    errors.append(
                        f"{label}: \"attached_to\" is {attached_to!r}, which is a "
                        f"{id_to_type[attached_to]} requirement, not an ACTION — a RULE's "
                        f"\"attached_to\" must name the action it governs"
                    )
            elif known_actions is not None and attached_to not in known_actions:
                errors.append(
                    f"{label}: \"attached_to\" is {attached_to!r}, which is neither an ACTION "
                    f"requirement id in this plan nor an existing action "
                    f"({sorted(known_actions)}) — a RULE attaches to the action it governs; "
                    f"anything about fishing itself (a ban, \"before the next trip\", \"from "
                    f"their catch\") governs the existing \"harvest\" action"
                )

        if req_type == "ROLE" and req.get("exclusive"):
            assigned_by = req.get("assigned_by")
            if not isinstance(assigned_by, list) or not assigned_by:
                errors.append(
                    f"{label}: an exclusive ROLE needs \"assigned_by\" — the requirement id(s) of "
                    f"the ACTION/RULE that actually grants this role to a specific agent. A role "
                    f"existing doesn't put anyone in it: without an assignment step, every action "
                    f"only its holder may take has no participants at all"
                )
            else:
                for ref in assigned_by:
                    if ref not in id_to_type:
                        errors.append(f"{label}: \"assigned_by\" names {ref!r}, which isn't a requirement id")
                    elif id_to_type[ref] not in ("ACTION", "RULE", "LIFECYCLE"):
                        errors.append(
                            f"{label}: \"assigned_by\" names {ref!r}, a {id_to_type[ref]} requirement — "
                            f"only an ACTION, RULE, or LIFECYCLE can grant a role"
                        )

        depends_on = req.get("depends_on", [])
        if not isinstance(depends_on, list):
            errors.append(f"{label}: \"depends_on\" must be a list of requirement ids")
            depends_on = []
        for dep in depends_on:
            if dep == req_id:
                errors.append(f"{label}: \"depends_on\" lists itself")
            elif dep not in id_to_type:
                errors.append(f"{label}: \"depends_on\" names {dep!r}, which isn't a requirement id")

        if req_type == "ACTION" and req.get("judgment_required"):
            context = req.get("decision_context")
            if not isinstance(context, dict) or not context.get("prompt_to") or not context.get("output"):
                errors.append(
                    f"{label}: an ACTION with judgment_required needs a \"decision_context\" "
                    f"with at least \"prompt_to\" (who exactly is asked) and \"output\" (what "
                    f"structured decision comes back) — plus whatever visible_state/"
                    f"visible_objects/visible_institutional_information/choices the decision "
                    f"actually needs"
                )

    errors += _norm_plan_dependency_cycle_errors(requirements, id_to_type)

    flows = plan.get("flows", [])
    if not isinstance(flows, list):
        errors.append("\"flows\" must be a list")
        flows = []
    for flow in flows:
        flow_label = f"flow {flow.get('id') or flow.get('name') or '?'!r}"
        steps = flow.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"{flow_label}: \"steps\" must be a non-empty list")
            continue
        for step in steps:
            step_req = step.get("requirement")
            if step_req not in id_to_type:
                errors.append(f"{flow_label}: step names requirement {step_req!r}, which doesn't exist")
            for key in ("after", "next"):
                for ref in step.get(key) or []:
                    if ref not in id_to_type:
                        errors.append(
                            f"{flow_label}: step {step_req!r}'s \"{key}\" names {ref!r}, which isn't a "
                            f"requirement id"
                        )

    coverage = plan.get("source_coverage")
    if not isinstance(coverage, list) or not coverage:
        errors.append(
            "\"source_coverage\" must be a non-empty list mapping every normative clause of "
            "norm.txt to the requirement ids implementing it — the plan's own proof that no "
            "clause silently disappeared"
        )
    else:
        for i, entry in enumerate(coverage):
            entry_label = f"source_coverage[{i}]"
            if not entry.get("source_clause"):
                errors.append(f"{entry_label}: missing \"source_clause\"")
            if entry.get("coverage") not in NORM_PLAN_COVERAGE_VALUES:
                errors.append(
                    f"{entry_label}: \"coverage\" is {entry.get('coverage')!r}, must be one of "
                    f"{sorted(NORM_PLAN_COVERAGE_VALUES)}"
                )
            for ref in entry.get("requirements") or []:
                if ref not in id_to_type:
                    errors.append(f"{entry_label}: names requirement {ref!r}, which doesn't exist")
            if entry.get("coverage") == "COVERED" and not entry.get("requirements"):
                errors.append(f"{entry_label}: marked COVERED but names no requirement ids")
    return errors


def _norm_clause_count(norm_text):
    """How many separately-coverable clauses the Operationalization has:
    its numbered items if numbered, else its sentences. (count, unit) or
    (0, None)."""
    if not norm_text:
        return 0, None
    marker = norm_text.find("Operationalization:")
    body = norm_text[marker + len("Operationalization:"):] if marker >= 0 else norm_text
    numbered = set(re.findall(r"(?:^|\s)(\d{1,2})[.)]\s", body))
    if len(numbered) >= 2:
        return len(numbered), "numbered clauses"
    sentences = [x for x in re.split(r"(?<=[.!?])\s+", body.strip()) if len(x.split()) >= 4]
    return len(sentences), "sentences"


def _norm_plan_clause_coverage_errors(plan, norm_text):
    count, unit = _norm_clause_count(norm_text)
    coverage = plan.get("source_coverage")
    if not count or not isinstance(coverage, list) or not coverage:
        return []  # missing/empty coverage is already reported by _norm_plan_reference_errors()
    if len(coverage) < count:
        return [
            f"\"source_coverage\" has {len(coverage)} entries, but norm.txt's Operationalization "
            f"has {count} {unit} — give each one its own entry (source_clause = that clause's own "
            f"text), so no clause can be silently folded into a broader one and marked COVERED"
        ]
    return []


def _norm_plan_dependency_cycle_errors(requirements, id_to_type):
    graph = {
        req.get("id"): [d for d in (req.get("depends_on") or []) if d in id_to_type and d != req.get("id")]
        for req in requirements if req.get("id") and isinstance(req.get("depends_on", []), list)
    }
    visiting, done, errors = set(), set(), []

    def visit(node, path):
        if node in done:
            return
        if node in visiting:
            cycle = path[path.index(node):] + [node]
            errors.append(f"\"depends_on\" forms a cycle: {' -> '.join(cycle)}")
            return
        visiting.add(node)
        for dep in graph.get(node, []):
            visit(dep, path + [node])
        visiting.discard(node)
        done.add(node)

    for node in graph:
        visit(node, [])
    return errors


def _known_institution_actions():
    institution_path = ROOT / "state" / "institution.json"
    try:
        return set(json.loads(institution_path.read_text()).get("actions", {}))
    except (OSError, json.JSONDecodeError):
        return None


def _known_institution_roles():
    institution_path = ROOT / "state" / "institution.json"
    try:
        return set(json.loads(institution_path.read_text()).get("roles", {}))
    except (OSError, json.JSONDecodeError):
        return set()


def _extract_fenced_block(text, lang):
    """Last fenced ```<lang> block in text, scanning from the end — never
    an earlier example block. None if there isn't one."""
    matches = re.findall(rf"```{lang}\s*\n(.*?)```", text, re.DOTALL)
    return matches[-1].strip() if matches else None


def _strip_json_comments_and_trailing_commas(text):
    """Drops // and /* */ comments and trailing commas before ] or },
    skipping anything inside a JSON string (a URL's "//", a "," in a
    value, are left alone)."""
    out, i, n, in_string = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        elif c == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "]}":
                i += 1
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _loads_llm_json(text):
    """json.loads(), falling back to the comment/trailing-comma-stripped
    copy if strict parsing fails — a model hand-annotating its own JSON
    output ("attached_to": "harvest",  // ...) shouldn't discard an
    otherwise-valid plan. Still raises json.JSONDecodeError if the
    cleaned text doesn't parse either."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_strip_json_comments_and_trailing_commas(text))


def _parse_architect_plan(raw_text):
    """(plan, None) for a usable plan, else (None, reason)."""
    plan_raw = _extract_fenced_block(raw_text, "json")
    if not plan_raw:
        return None, "the response contained no ```json block"
    try:
        plan = _loads_llm_json(plan_raw)
    except json.JSONDecodeError as exc:
        return None, f"the ```json block isn't valid JSON ({exc})"
    if not isinstance(plan, dict) or "requirements" not in plan:
        return None, "the ```json block has no top-level \"requirements\" key"
    return plan, None


def _apply_clarification_patch(plan, patch_text, note):
    """Parses one scoped clarification-patch response (contract: see
    NORM_ARCHITECT_CLARIFICATION_SYSTEM_PROMPT, engine/llm_agents.py) and,
    if structurally sound, merges it into `plan` -> (merged_plan, None).
    (None, reason) on any failure, so the caller can keep `plan` as-is.

    The guarantee: an object from the patch's own "requirements" only
    lands if its id is in "affected_requirements"/"added_requirements" —
    every other id is copied *verbatim* from the original plan, by
    object identity. A model can't make an undeclared edit land; the
    harness decides what changed, not the model's own account of itself.

    `note` (the critique or the structural errors being fixed) is
    appended to plan["clarifications"] for traceability only — never
    read back by anything downstream."""
    patch_raw = _extract_fenced_block(patch_text, "json")
    try:
        patch = _loads_llm_json(patch_raw) if patch_raw else None
    except json.JSONDecodeError:
        return None, "clarification response had no parseable ```json block"
    if not isinstance(patch, dict):
        return None, "clarification response's json block wasn't an object"

    # A patch touching only source_coverage/flows has nothing to put in
    # affected_requirements/requirements — an absent key defaults to
    # empty rather than invalidating an otherwise-correct patch; a
    # present key of the wrong type is still a real error.
    affected = patch.get("affected_requirements")
    if affected is None:
        affected = []
    unchanged = patch.get("unchanged_requirements")
    if unchanged is None:
        unchanged = []
    new_requirements = patch.get("requirements")
    if new_requirements is None:
        new_requirements = []
    if not isinstance(affected, list) or not isinstance(unchanged, list) or not isinstance(new_requirements, list):
        return None, (
            "clarification response's affected_requirements/unchanged_requirements/"
            "requirements, when present, must be lists"
        )

    original_ids = {req.get("id") for req in plan.get("requirements", []) if req.get("id")}
    affected_ids = set(affected)
    unchanged_ids = set(unchanged)

    overlap = affected_ids & unchanged_ids
    if overlap:
        return None, f"affected_requirements and unchanged_requirements overlap: {sorted(overlap)}"

    if (affected_ids | unchanged_ids) != original_ids:
        missing = original_ids - (affected_ids | unchanged_ids)
        extra = (affected_ids | unchanged_ids) - original_ids
        return None, (
            f"affected_requirements + unchanged_requirements don't account for exactly the "
            f"plan's own requirement ids — missing {sorted(missing)}, unexpected {sorted(extra)}"
        )

    # A patch may add brand-new requirements too — a coverage gap or an
    # undecomposed group decision needs one; existing ids still only
    # change via affected_requirements.
    added = patch.get("added_requirements") or []
    if not isinstance(added, list):
        return None, "\"added_requirements\" must be a list"
    added_ids = set(added)
    clashing = added_ids & original_ids
    if clashing:
        return None, (
            f"added_requirements names id(s) already in the plan: {sorted(clashing)} — use "
            f"affected_requirements to change an existing requirement"
        )

    new_by_id = {req.get("id"): req for req in new_requirements if req.get("id")}
    if set(new_by_id) != affected_ids | added_ids:
        return None, (
            f"\"requirements\" in the patch don't match affected_requirements + "
            f"added_requirements exactly — patch has {sorted(new_by_id)}, declared "
            f"{sorted(affected_ids | added_ids)}"
        )

    merged_requirements = [
        new_by_id[req["id"]] if req.get("id") in affected_ids else req
        for req in plan.get("requirements", [])
    ] + [req for req in new_requirements if req.get("id") in added_ids]
    merged_plan = {**plan, "requirements": merged_requirements}
    # flows/source_coverage are whole-plan views, not per-requirement —
    # a patch replaces each wholesale when it includes one; the
    # validator re-checks every reference against the merged ids after.
    for key in ("flows", "source_coverage"):
        if key in patch:
            if not isinstance(patch[key], list):
                return None, f"\"{key}\" in the patch must be a list"
            merged_plan[key] = patch[key]
    merged_plan["clarifications"] = list(plan.get("clarifications") or [])
    clarification = {
        "clarification_for": patch.get("clarification_for"),
        "affected_requirements": sorted(affected_ids),
        "unchanged_requirements": sorted(unchanged_ids),
        "note": note,
    }
    if added_ids:
        clarification["added_requirements"] = sorted(added_ids)
    replaced = [key for key in ("flows", "source_coverage") if key in patch]
    if replaced:
        clarification["replaced"] = replaced
    merged_plan["clarifications"].append(clarification)
    return merged_plan, None
